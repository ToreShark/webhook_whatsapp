import { Controller, Get, Post, Req, Res, HttpStatus, Logger, OnModuleInit } from '@nestjs/common';
import { Request, Response } from 'express';
import { ChatSessionService } from './services/chat-session.service';
import { ConsultationSlotService } from './services/consultation-slot.service';

@Controller()
export class WebhookController implements OnModuleInit {
  private readonly logger = new Logger(WebhookController.name);
  
  constructor(
    private readonly chatSessionService: ChatSessionService,
    private readonly consultationSlotService: ConsultationSlotService
  ) {}

  async onModuleInit() {
    // Инициализируем слоты при запуске приложения
    await this.consultationSlotService.initializeSlots();
  }

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
      
      // Проверяем тип сообщения - текст или кнопка
      let messageBody = '';
      let isHandled = false;

      if (message.text?.body) {
        messageBody = message.text.body; // обычное текстовое сообщение
      } else if (message.interactive?.button_reply) {
        // Нажатие на Quick Reply кнопку
        const buttonId = message.interactive.button_reply.id;
        isHandled = await this.handleButtonClick(buttonId, from);

        // Если кнопка не была обработана напрямую, получаем сообщение для RAG
        if (!isHandled) {
          messageBody = this.getButtonMessage(buttonId);
        }
      } else if (message.audio || message.voice) {
        // Голосовое сообщение - отправляем предупреждение
        await this.sendWhatsAppMessage(
          from,
          '⚠️ Бот не может обработать голосовые сообщения.\n\nПожалуйста, напишите ваш вопрос текстом. Бот поддерживает только русский язык и текстовые сообщения.'
        );
        isHandled = true;
      }

      this.logger.log(`Message from ${from}: ${messageBody || 'Button handled directly'}`);

      // Обрабатываем сообщение через RAG только если не обработали напрямую
      if (messageBody && !isHandled) {
        await this.processMessage(from, messageBody);
      }
    }

    return res.status(HttpStatus.OK).end();
  }

  private async handleButtonClick(buttonId: string, whatsappId: string): Promise<boolean> {
    // Если это кнопка записи на консультацию - обрабатываем отдельно
    if (buttonId === 'consultation_btn') {
      await this.handleConsultationRequest(whatsappId);
      return true; // Обработали, не нужно передавать в RAG
    }

    // Если это выбор слота - обрабатываем бронирование
    if (buttonId.startsWith('slot_')) {
      await this.handleSlotBooking(whatsappId, buttonId);
      return true; // Обработали, не нужно передавать в RAG
    }

    // Если это кнопка покупки курса
    if (buttonId === 'course_btn') {
      await this.handleCourseRequest(whatsappId);
      return true; // Обработали, не нужно передавать в RAG
    }

    // Если это кнопка покупки учебника
    if (buttonId === 'textbook_btn') {
      await this.handleTextbookRequest(whatsappId);
      return true; // Обработали, не нужно передавать в RAG
    }

    // Для остальных кнопок возвращаем false, чтобы передать в RAG
    return false;
  }

  private getButtonMessage(buttonId: string): string {
    switch (buttonId) {
      case 'course_btn':
        return 'Хочу купить курс по банкротству';
      case 'more_info_btn':
        return 'Хочу узнать больше информации';
      default:
        return 'Неизвестная команда';
    }
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
      if (ragResponse.completion_status === 'complete') {
        // Если консультация завершена, отправляем с кнопками
        await this.sendWhatsAppMessageWithButtons(whatsappId, ragResponse.response);
      } else {
        // Обычное сообщение без кнопок
        await this.sendWhatsAppMessage(whatsappId, ragResponse.response);
      }
      
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

  private async sendWhatsAppMessageWithButtons(to: string, text: string) {
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
          type: 'interactive',
          interactive: {
            type: 'button',
            body: {
              text: text
            },
            action: {
              buttons: [
                {
                  type: 'reply',
                  reply: {
                    id: 'consultation_btn',
                    title: 'Записаться'
                  }
                },
                {
                  type: 'reply',
                  reply: {
                    id: 'course_btn', 
                    title: 'Купить курс'
                  }
                },
                {
                  type: 'reply',
                  reply: {
                    id: 'textbook_btn',
                    title: 'Купить учебник'
                  }
                }
              ]
            }
          }
        }),
      });

      const result = await response.json();
      this.logger.log('WhatsApp message with buttons sent:', result);
    } catch (error) {
      this.logger.error('Error sending WhatsApp message with buttons:', error);
    }
  }

  // Обработка запроса на консультацию
  private async handleConsultationRequest(whatsappId: string) {
    try {
      // Получаем доступные слоты на ближайший день
      const availableDay = await this.consultationSlotService.getSlotsForNearestAvailableDay();

      if (!availableDay) {
        await this.sendWhatsAppMessage(
          whatsappId,
          'К сожалению, в ближайшее время нет свободных слотов для консультации. Попробуйте позже.'
        );
        return;
      }

      // Формируем сообщение со слотами
      let message = `📅 Доступные слоты на консультацию\n\n${availableDay.dateString}\n\nВыберите удобное время:`;

      // Создаем кнопки для каждого слота
      const buttons = availableDay.slots.map((slot) => ({
        type: 'reply',
        reply: {
          id: slot.slotId,
          title: `${slot.startTime}-${slot.endTime}`
        }
      }));

      await this.sendWhatsAppMessageWithSlotButtons(whatsappId, message, buttons);

    } catch (error) {
      this.logger.error('Error handling consultation request:', error);
      await this.sendWhatsAppMessage(
        whatsappId,
        'Произошла ошибка при получении доступных слотов. Попробуйте позже.'
      );
    }
  }

  // Обработка бронирования слота
  private async handleSlotBooking(whatsappId: string, slotId: string) {
    try {
      // Пытаемся забронировать слот
      const bookedSlot = await this.consultationSlotService.bookSlot(
        slotId,
        whatsappId,
        'session_' + Date.now() // временный ID сессии
      );

      if (bookedSlot) {
        const slotTime = this.consultationSlotService.formatSlotForDisplay(bookedSlot);
        await this.sendWhatsAppMessage(
          whatsappId,
          `✅ Отлично! Вы записаны на консультацию:\n\n📅 ${slotTime}\n\nМы свяжемся с вами за день до консультации для подтверждения. Если у вас есть вопросы, напишите нам.`
        );
      } else {
        await this.sendWhatsAppMessage(
          whatsappId,
          '❌ К сожалению, этот слот уже занят. Попробуйте выбрать другое время.'
        );
      }

    } catch (error) {
      this.logger.error('Error booking slot:', error);
      await this.sendWhatsAppMessage(
        whatsappId,
        'Произошла ошибка при бронировании. Попробуйте еще раз.'
      );
    }
  }

  // Отправка сообщения с кнопками слотов
  private async sendWhatsAppMessageWithSlotButtons(to: string, text: string, buttons: any[]) {
    const accessToken = process.env.ACCESS_TOKEN;
    const phoneNumberId = '818293204692583';

    try {
      // WhatsApp поддерживает максимум 3 кнопки за раз
      // Если слотов больше, отправляем по частям
      const buttonChunks = [];
      for (let i = 0; i < buttons.length; i += 3) {
        buttonChunks.push(buttons.slice(i, i + 3));
      }

      for (let chunkIndex = 0; chunkIndex < buttonChunks.length; chunkIndex++) {
        const chunk = buttonChunks[chunkIndex];
        const chunkMessage = chunkIndex === 0 ? text : `Продолжение (часть ${chunkIndex + 1}):`;

        const response = await fetch(`https://graph.facebook.com/v23.0/${phoneNumberId}/messages`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            messaging_product: 'whatsapp',
            to: to,
            type: 'interactive',
            interactive: {
              type: 'button',
              body: {
                text: chunkMessage
              },
              action: {
                buttons: chunk
              }
            }
          }),
        });

        const result = await response.json();
        this.logger.log(`WhatsApp slot buttons sent (chunk ${chunkIndex + 1}):`, result);
      }

    } catch (error) {
      this.logger.error('Error sending WhatsApp message with slot buttons:', error);
    }
  }

  // Обработка запроса на покупку курса
  private async handleCourseRequest(whatsappId: string) {
    try {
      const courseMessage = `🎥 **ВИДЕОКУРС ПО БАНКРОТСТВУ ГРАЖДАН РК**

📚 **Что включено в курс:**
• Пошаговые видеоуроки по всем процедурам банкротства
• Практические примеры и реальные кейсы
• Разбор частых ошибок и как их избежать
• Образцы всех необходимых документов
• Консультации с экспертами-практиками
• Доступ к материалам на 12 месяцев

💡 **Для кого подходит:**
• Граждане, рассматривающие банкротство
• Юристы, изучающие банкротное право
• Предприниматели с долговыми обязательствами

🔗 **Перейти к покупке:**
https://primelegal.kz/Subcategory/Index/kurs-bankrotstvo-grazhdan-rk

📞 **Есть вопросы?** Запишитесь на консультацию к адвокату Мухтарову Торехану для получения персональных рекомендаций.`;

      await this.sendWhatsAppMessage(whatsappId, courseMessage);

    } catch (error) {
      this.logger.error('Error handling course request:', error);
      await this.sendWhatsAppMessage(
        whatsappId,
        'Произошла ошибка при получении информации о курсе. Попробуйте позже.'
      );
    }
  }

  // Обработка запроса на покупку учебника
  private async handleTextbookRequest(whatsappId: string) {
    try {
      const textbookMessage = `📖 **УЧЕБНИК ПО БАНКРОТСТВУ ФИЗИЧЕСКИХ ЛИЦ (2025)**

📋 **Полное практическое руководство включает:**
• Актуальные изменения в законодательстве 2025 года
• Условия и критерии для всех видов банкротства
• Детальный разбор внесудебного банкротства
• Пошаговая инструкция судебного банкротства
• Процедура восстановления платежеспособности
• Реальная судебная практика с комментариями
• Образцы заявлений и документов

💼 **Особенности издания:**
• Написан практикующими юристами
• Актуальная судебная практика
• Понятный язык изложения
• Готовые шаблоны документов

🔗 **Купить учебник:**
https://primelegal.kz/details/bankrotstvo-fizlic-kazakhstan-uchebnik-2025-3590-1

✨ **Рекомендация:** Для максимального эффекта изучите учебник, а затем запишитесь на консультацию к адвокату Мухтарову Торехану для разбора вашей конкретной ситуации.`;

      await this.sendWhatsAppMessage(whatsappId, textbookMessage);

    } catch (error) {
      this.logger.error('Error handling textbook request:', error);
      await this.sendWhatsAppMessage(
        whatsappId,
        'Произошла ошибка при получении информации об учебнике. Попробуйте позже.'
      );
    }
  }
}