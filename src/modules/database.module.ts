import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { ChatSession, ChatSessionSchema } from '../schemas/chat-session.schema';
import { ConsultationSlot, ConsultationSlotSchema } from '../schemas/consultation-slot.schema';
import { ChatSessionService } from '../services/chat-session.service';
import { ConsultationSlotService } from '../services/consultation-slot.service';

@Module({
  imports: [
    MongooseModule.forRoot(
      process.env.MONGODB_URI || 
      'mongodb+srv://new_user_blya:2AKHOE1lpZYSoPru@cluster0.lgtepjy.mongodb.net/whatsapp_bankruptcy_bot?retryWrites=true&w=majority'
    ),
    MongooseModule.forFeature([
      { name: ChatSession.name, schema: ChatSessionSchema },
      { name: ConsultationSlot.name, schema: ConsultationSlotSchema }
    ])
  ],
  providers: [ChatSessionService, ConsultationSlotService],
  exports: [ChatSessionService, ConsultationSlotService]
})
export class DatabaseModule {}