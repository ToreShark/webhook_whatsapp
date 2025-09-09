import { Controller, Get, Post, Req, Res, HttpStatus, Logger } from '@nestjs/common';
import { Request, Response } from 'express';

@Controller()
export class WebhookController {
  private readonly logger = new Logger(WebhookController.name);

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

      // Отправляем автоответ
      if (messageBody) {
        await this.sendWhatsAppMessage(from, `Привет! Ты написал: "${messageBody}"`);
      }
    }

    return res.status(HttpStatus.OK).end();
  }

  private async sendWhatsAppMessage(to: string, text: string) {
    const accessToken = process.env.ACCESS_TOKEN;
    const phoneNumberId = '818293204692583'; // из твоего curl запроса

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