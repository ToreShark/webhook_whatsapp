import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type ChatSessionDocument = ChatSession & Document;

@Schema({ timestamps: true })
export class ChatSession {
  @Prop({ required: true, unique: true, index: true })
  whatsappId!: string;

  @Prop({ 
    required: true, 
    enum: ['initial', 'collecting_info', 'answered', 'offering_product'],
    default: 'initial'
  })
  sessionState!: string;

  @Prop({ type: Object, default: {} })
  context!: {
    debtAmount?: number;
    hasIncome?: boolean;
    incomeAmount?: number;
    incomeStable?: boolean;
    hasOverdue12Months?: boolean;
    questionsAsked: string[];
    answersReceived: Record<string, any>;
    userIntent?: string;
    currentTopic?: string;
  };

  @Prop({ type: Array, default: [] })
  history!: Array<{
    message: string;
    sender: 'user' | 'bot';
    timestamp: Date;
  }>;

  @Prop({ default: Date.now })
  lastActivity!: Date;
}

export const ChatSessionSchema = SchemaFactory.createForClass(ChatSession);