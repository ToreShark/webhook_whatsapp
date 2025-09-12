import { Controller, Get, Post, Req, Res, HttpStatus, Logger } from '@nestjs/common';
import { Request, Response } from 'express';
import { ChatSessionService } from './services/chat-session.service';

@Controller()
export class WebhookController {
  private readonly logger = new Logger(WebhookController.name);
  
  constructor(private readonly chatSessionService: ChatSessionService) {}

  @Get()
  verify(@Req() req: Request, @Res() res: Response) {
    const mode = req.query['hub.mode'];
    const challenge = req.query['hub.challenge'];
    const token = req.query['hub.verify_token'];
    const verifyToken = process.env.VERIFY_TOKEN;

    this.logger.log(`VERIFICATION ATTEMPT:`);
    this.logger.log(`- mode: ${mode}`);
    this.logger.log(`- challenge: ${challenge}`);
    this.logger.log(`- received token: ${token}`);
    this.logger.log(`- expected token: ${verifyToken}`);

    if (mode === 'subscribe' && token === verifyToken) {
      this.logger.log('✅ WEBHOOK VERIFIED');
      return res.status(HttpStatus.OK).send(challenge);
    }
    this.logger.log('❌ WEBHOOK VERIFICATION FAILED');
    return res.status(HttpStatus.FORBIDDEN).end();
  }

  @Post()
  async receive(@Req() req: Request, @Res() res: Response) {
    const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
    this.logger.log(`\nWebhook received ${ts}`);
    this.logger.log(JSON.stringify(req.body, null, 2));

    // Обработка входящих сообщений
    const { entry } = req.body;
    if (entry && entry[0]?.changes && entry[0].changes[0]?.value?.messages) {
      const message = entry[0].changes[0].value.messages[0];
      const from = message.from; // номер отправителя
      const messageBody = message.text?.body; // текст сообщения

      this.logger.log(`Message from ${from}: ${messageBody}`);

      // Обрабатываем сообщение через RAG
      if (messageBody) {
        await this.processMessage(from, messageBody);
      }
    }

    return res.status(HttpStatus.OK).end();
  }

  private async processMessage(whatsappId: string, message: string) {
    try {
      // Получаем или создаем сессию
      const session = await this.chatSessionService.getOrCreateSession(whatsappId);
      
      // Сохраняем сообщение пользователя в историю
      await this.chatSessionService.addToHistory(whatsappId, message, 'user');

      // Отправляем запрос в Python RAG
      const pythonRagUrl = process.env.PYTHON_RAG_URL || 'http://python-rag:8000';
      const response = await fetch(`${pythonRagUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          whatsapp_id: whatsappId,
          message: message,
          context: session.context,
          session_state: session.sessionState
        }),
      });

      if (!response.ok) {
        throw new Error(`RAG service error: ${response.status}`);
      }

      const ragResponse = await response.json();
      
      // Обновляем состояние сессии
      await this.chatSessionService.updateSessionState(whatsappId, ragResponse.session_state);
      
      // Обновляем контекст если есть изменения
      if (ragResponse.context_updates && Object.keys(ragResponse.context_updates).length > 0) {
        await this.chatSessionService.updateContext(whatsappId, ragResponse.context_updates);
      }
      
      // Сохраняем заданный вопрос если есть
      if (ragResponse.next_question) {
        await this.chatSessionService.addQuestionAsked(whatsappId, ragResponse.next_question);
      }
      
      // Отправляем ответ пользователю
      await this.sendWhatsAppMessage(whatsappId, ragResponse.response);
      
      // Сохраняем ответ бота в историю
      await this.chatSessionService.addToHistory(whatsappId, ragResponse.response, 'bot');
      
      // Логируем статус завершения для отладки
      if (ragResponse.completion_status) {
        this.logger.log(`Completion status for ${whatsappId}:`, ragResponse.completion_status);
      }
      
    } catch (error) {
      this.logger.error('Error processing message:', error);
      await this.sendWhatsAppMessage(whatsappId, 
        'Извините, произошла ошибка. Попробуйте еще раз или напишите /start для начала новой консультации.'
      );
    }
  }


  private async sendWhatsAppMessage(to: string, text: string) {
    const accessToken = process.env.ACCESS_TOKEN;
    const phoneNumberId = '818293204692583';

    try {
      const response = await fetch(`https://graph.facebook.com/v23.0/${phoneNumberId}/messages`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messaging_product: 'whatsapp',
          to: to,
          type: 'text',
          text: { body: text }
        }),
      });

      const result = await response.json();
      this.logger.log('WhatsApp message sent:', result);
    } catch (error) {
      this.logger.error('Error sending WhatsApp message:', error);
    }
  }
}