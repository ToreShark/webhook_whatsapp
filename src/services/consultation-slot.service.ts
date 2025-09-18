import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { ConsultationSlot, ConsultationSlotDocument } from '../schemas/consultation-slot.schema';
import { v4 as uuidv4 } from 'uuid';
import { Cron, CronExpression } from '@nestjs/schedule';

@Injectable()
export class ConsultationSlotService implements OnModuleInit {
  private readonly logger = new Logger(ConsultationSlotService.name);
  
  // Конфигурация рабочих часов
  private readonly WORK_START_HOUR = 12; // 12:00
  private readonly WORK_END_HOUR = 18;   // 18:00
  private readonly SLOT_DURATION = 60;   // 60 минут
  private readonly PLANNING_DAYS = 7;    // Планирование на 7 дней вперед

  constructor(
    @InjectModel(ConsultationSlot.name)
    private consultationSlotModel: Model<ConsultationSlotDocument>
  ) {}

  // Метод вызывается автоматически при запуске приложения
  async onModuleInit() {
    this.logger.log('Application started - initializing consultation slots...');
    await this.initializeSlots();
  }

  // CRON задача - запускается каждый день в 00:01
  @Cron('1 0 * * *')
  async generateDailySlots() {
    this.logger.log('Starting daily slot generation...');
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    // Генерируем слоты на следующие 7 дней
    for (let dayOffset = 0; dayOffset <= this.PLANNING_DAYS; dayOffset++) {
      const targetDate = new Date(today);
      targetDate.setDate(today.getDate() + dayOffset);
      
      // Пропускаем выходные (суббота = 6, воскресенье = 0)
      const dayOfWeek = targetDate.getDay();
      if (dayOfWeek === 0 || dayOfWeek === 6) {
        this.logger.log(`Skipping weekend day: ${targetDate.toDateString()}`);
        continue;
      }
      
      // Генерируем слоты для рабочего дня
      await this.generateSlotsForDay(targetDate);
    }
    
    this.logger.log('Daily slot generation completed');
  }

  private async generateSlotsForDay(date: Date) {
    const slots = [];
    
    // Генерируем слоты с 12:00 до 18:00 с интервалом в 1 час
    for (let hour = this.WORK_START_HOUR; hour < this.WORK_END_HOUR; hour++) {
      const startTime = `${hour.toString().padStart(2, '0')}:00`;
      const endHour = hour + 1;
      const endTime = `${endHour.toString().padStart(2, '0')}:00`;
      
      // Проверяем, существует ли уже такой слот
      const existingSlot = await this.consultationSlotModel.findOne({
        date: date,
        startTime: startTime
      });
      
      if (!existingSlot) {
        const slotId = `slot_${date.toISOString().split('T')[0]}_${startTime.replace(':', '')}_${uuidv4().substring(0, 8)}`;
        
        slots.push({
          slotId,
          date,
          startTime,
          endTime,
          status: 'open'
        });
      }
    }
    
    // Сохраняем новые слоты
    if (slots.length > 0) {
      try {
        await this.consultationSlotModel.insertMany(slots);
        this.logger.log(`Created ${slots.length} slots for ${date.toDateString()}`);
      } catch (error) {
        this.logger.error(`Error creating slots for ${date.toDateString()}:`, error);
      }
    } else {
      this.logger.log(`No new slots needed for ${date.toDateString()}`);
    }
  }

  // Метод для получения доступных слотов
  async getAvailableSlots(days: number = 7): Promise<ConsultationSlotDocument[]> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const endDate = new Date(today);
    endDate.setDate(today.getDate() + days);

    return await this.consultationSlotModel
      .find({
        date: {
          $gte: today,
          $lte: endDate
        },
        status: 'open'
      })
      .sort({ date: 1, startTime: 1 })
      .exec();
  }

  // Метод для получения слотов на ближайший доступный день
  async getSlotsForNearestAvailableDay(): Promise<{
    date: Date;
    slots: ConsultationSlotDocument[];
    dateString: string;
  } | null> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Ищем слоты на ближайшие 30 дней
    for (let dayOffset = 0; dayOffset < 30; dayOffset++) {
      const targetDate = new Date(today);
      targetDate.setDate(today.getDate() + dayOffset);

      // Находим доступные слоты на эту дату
      const availableSlots = await this.consultationSlotModel
        .find({
          date: targetDate,
          status: 'open'
        })
        .sort({ startTime: 1 })
        .exec();

      // Если есть доступные слоты, возвращаем их
      if (availableSlots.length > 0) {
        const dateString = targetDate.toLocaleDateString('ru-RU', {
          weekday: 'long',
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        });

        return {
          date: targetDate,
          slots: availableSlots,
          dateString
        };
      }
    }

    return null; // Нет доступных слотов в ближайшие 30 дней
  }

  // Метод для бронирования слота
  async bookSlot(
    slotId: string, 
    whatsappId: string, 
    sessionId: string,
    userName?: string,
    userPhone?: string
  ): Promise<ConsultationSlotDocument | null> {
    const slot = await this.consultationSlotModel.findOneAndUpdate(
      {
        slotId,
        status: 'open'
      },
      {
        $set: {
          status: 'booked',
          whatsappId,
          sessionId,
          userName,
          userPhone,
          bookingTime: new Date()
        }
      },
      { new: true }
    );
    
    if (slot) {
      this.logger.log(`Slot ${slotId} booked by ${whatsappId}`);
    } else {
      this.logger.warn(`Failed to book slot ${slotId} - may already be booked`);
    }
    
    return slot;
  }

  // Метод для отмены бронирования
  async cancelBooking(slotId: string, whatsappId: string): Promise<boolean> {
    const result = await this.consultationSlotModel.updateOne(
      {
        slotId,
        whatsappId,
        status: 'booked'
      },
      {
        $set: {
          status: 'open'
        },
        $unset: {
          whatsappId: 1,
          sessionId: 1,
          userName: 1,
          userPhone: 1,
          bookingTime: 1
        }
      }
    );
    
    if (result.modifiedCount > 0) {
      this.logger.log(`Booking cancelled for slot ${slotId}`);
      return true;
    }
    
    return false;
  }

  // Метод для получения забронированных слотов пользователя
  async getUserBookings(whatsappId: string): Promise<ConsultationSlotDocument[]> {
    return await this.consultationSlotModel
      .find({
        whatsappId,
        status: 'booked'
      })
      .sort({ date: 1, startTime: 1 })
      .exec();
  }

  // Метод для форматирования слотов в читаемый вид
  formatSlotForDisplay(slot: ConsultationSlotDocument): string {
    const date = new Date(slot.date);
    const dateStr = date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      weekday: 'short'
    });
    
    return `${dateStr} с ${slot.startTime} до ${slot.endTime}`;
  }

  // Метод для инициализации слотов при запуске приложения
  async initializeSlots() {
    this.logger.log('=================================');
    this.logger.log('STARTING SLOT INITIALIZATION');
    this.logger.log('=================================');
    this.logger.log(`Creating slots for next ${this.PLANNING_DAYS} days...`);
    this.logger.log(`Work hours: ${this.WORK_START_HOUR}:00 - ${this.WORK_END_HOUR}:00`);

    await this.generateDailySlots();

    const totalSlots = await this.consultationSlotModel.countDocuments();
    const availableSlots = await this.consultationSlotModel.countDocuments({ status: 'open' });

    this.logger.log('=================================');
    this.logger.log('SLOT INITIALIZATION COMPLETED');
    this.logger.log(`Total slots in database: ${totalSlots}`);
    this.logger.log(`Available slots: ${availableSlots}`);
    this.logger.log('=================================');
  }
}