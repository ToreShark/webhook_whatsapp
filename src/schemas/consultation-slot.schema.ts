import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type ConsultationSlotDocument = ConsultationSlot & Document;

@Schema({ timestamps: true })
export class ConsultationSlot {
  @Prop({ required: true, unique: true, index: true })
  slotId!: string;

  @Prop({ required: true, index: true })
  date!: Date; // Дата слота (только дата без времени)

  @Prop({ required: true })
  startTime!: string; // Время начала в формате "HH:mm" (например "14:00")

  @Prop({ required: true })
  endTime!: string; // Время окончания в формате "HH:mm" (например "15:00")

  @Prop({ 
    required: true, 
    enum: ['open', 'booked', 'completed', 'cancelled'],
    default: 'open'
  })
  status!: string;

  @Prop({ index: true })
  whatsappId?: string; // ID пользователя WhatsApp, который забронировал слот

  @Prop()
  sessionId?: string; // ID сессии чата

  @Prop()
  userName?: string; // Имя пользователя (если известно)

  @Prop()
  userPhone?: string; // Телефон пользователя для связи

  @Prop()
  bookingTime?: Date; // Время бронирования слота

  @Prop()
  notes?: string; // Заметки о консультации
}

export const ConsultationSlotSchema = SchemaFactory.createForClass(ConsultationSlot);

// Создаем составной индекс для предотвращения дубликатов
ConsultationSlotSchema.index({ date: 1, startTime: 1 }, { unique: true });