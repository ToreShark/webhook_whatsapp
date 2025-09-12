import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { ChatSession, ChatSessionDocument } from '../schemas/chat-session.schema';

@Injectable()
export class ChatSessionService {
  constructor(
    @InjectModel(ChatSession.name) 
    private chatSessionModel: Model<ChatSessionDocument>
  ) {}

  async getOrCreateSession(whatsappId: string): Promise<ChatSessionDocument> {
    let session = await this.chatSessionModel.findOne({ whatsappId });
    
    if (!session) {
      session = new this.chatSessionModel({
        whatsappId,
        sessionState: 'initial',
        context: {
          // Обязательные поля для принятия решения
          debtAmount: null,
          hasOverdue12Months: null,
          monthlyIncome: null,
          employmentType: null, // "official" | "unofficial" | "government" | "retired" | "unemployed" | "self_employed" | "maternity_leave"
          
          // Важные уточняющие поля
          incomeStability: null,
          hasProperty: null,
          hasCar: null,
          hasCollateral: null,
          collateralType: null,
          creditorsCount: null,
          
          // Специальные ситуации
          hasCollectorPressure: null,
          hasAccountArrest: null,
          hasWageArrest: null,
          previousRejection: null,
          
          // Системные поля
          questionsAsked: [],
          answersReceived: {},
          userIntent: null,
          currentTopic: null,
          lastExtraction: null,
          collectionPhase: null
        },
        history: [],
        lastActivity: new Date()
      });
      await session.save();
    } else {
      session.lastActivity = new Date();
      await session.save();
    }
    
    return session;
  }

  async updateSessionState(
    whatsappId: string, 
    state: 'initial' | 'collecting_info' | 'answered' | 'offering_product'
  ): Promise<boolean> {
    const result = await this.chatSessionModel.updateOne(
      { whatsappId },
      { 
        $set: { 
          sessionState: state,
          lastActivity: new Date()
        }
      }
    );
    return result.modifiedCount > 0;
  }

  async addToHistory(
    whatsappId: string, 
    message: string, 
    sender: 'user' | 'bot'
  ): Promise<boolean> {
    const result = await this.chatSessionModel.updateOne(
      { whatsappId },
      {
        $push: {
          history: {
            message,
            sender,
            timestamp: new Date()
          }
        },
        $set: { lastActivity: new Date() }
      }
    );
    return result.modifiedCount > 0;
  }

  async updateContext(
    whatsappId: string, 
    contextUpdates: Partial<ChatSession['context']>
  ): Promise<boolean> {
    const session = await this.getOrCreateSession(whatsappId);
    const currentContext = session.context || {};
    
    const updatedContext = {
      ...currentContext,
      ...contextUpdates
    };

    const result = await this.chatSessionModel.updateOne(
      { whatsappId },
      {
        $set: {
          context: updatedContext,
          lastActivity: new Date()
        }
      }
    );
    return result.modifiedCount > 0;
  }

  async addQuestionAsked(whatsappId: string, question: string): Promise<boolean> {
    const session = await this.getOrCreateSession(whatsappId);
    const questionsAsked = session.context?.questionsAsked || [];
    
    if (!questionsAsked.includes(question)) {
      questionsAsked.push(question);
      return await this.updateContext(whatsappId, { questionsAsked });
    }
    return false;
  }

  async saveAnswer(whatsappId: string, key: string, value: any): Promise<boolean> {
    const session = await this.getOrCreateSession(whatsappId);
    const answersReceived = session.context?.answersReceived || {};
    
    answersReceived[key] = value;
    return await this.updateContext(whatsappId, { answersReceived });
  }

  async resetSession(whatsappId: string): Promise<boolean> {
    const result = await this.chatSessionModel.updateOne(
      { whatsappId },
      {
        $set: {
          sessionState: 'initial',
          context: {
            // Обязательные поля для принятия решения
            debtAmount: null,
            hasOverdue12Months: null,
            monthlyIncome: null,
            employmentType: null, // "official" | "unofficial" | "government" | "retired" | "unemployed" | "self_employed" | "maternity_leave"
            
            // Важные уточняющие поля
            incomeStability: null,
            hasProperty: null,
            hasCar: null,
            hasCollateral: null,
            collateralType: null,
            creditorsCount: null,
            
            // Специальные ситуации
            hasCollectorPressure: null,
            hasAccountArrest: null,
            hasWageArrest: null,
            previousRejection: null,
            
            // Системные поля
            questionsAsked: [],
            answersReceived: {},
            userIntent: null,
            currentTopic: null,
            lastExtraction: null,
            collectionPhase: null
          },
          history: [],
          lastActivity: new Date()
        }
      }
    );
    return result.modifiedCount > 0;
  }

  async getAllSessions(limit: number = 100): Promise<ChatSessionDocument[]> {
    return await this.chatSessionModel
      .find()
      .sort({ lastActivity: -1 })
      .limit(limit)
      .exec();
  }

  async getSessionContext(whatsappId: string): Promise<ChatSession['context'] | null> {
    const session = await this.chatSessionModel.findOne({ whatsappId });
    return session?.context || null;
  }
}