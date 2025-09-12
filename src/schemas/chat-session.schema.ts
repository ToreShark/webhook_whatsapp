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
    // Обязательные поля для принятия решения
    debtAmount?: number;
    hasOverdue12Months?: boolean;
    monthlyIncome?: number;
    employmentType?: string; // "official" | "unofficial" | "government" | "retired" | "unemployed" | "self_employed"
    
    // Важные уточняющие поля
    incomeStability?: string; // "stable" | "unstable"
    hasProperty?: boolean;
    hasCar?: boolean;
    hasCollateral?: boolean;
    collateralType?: string; // "mortgage" | "auto_loan" | "other"
    creditorsCount?: number;
    
    // Специальные ситуации
    hasCollectorPressure?: boolean;
    hasAccountArrest?: boolean;
    hasWageArrest?: boolean;
    previousRejection?: boolean;
    
    // Системные поля
    questionsAsked: string[];
    answersReceived: Record<string, any>;
    userIntent?: string; // "eligibility_check" | "how_to_start" | "documentation" | "consequences" | "specific_problem"
    currentTopic?: string;
    lastExtraction?: Record<string, any>;
    collectionPhase?: string; // "collecting" | "analyzing" | "complete"
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