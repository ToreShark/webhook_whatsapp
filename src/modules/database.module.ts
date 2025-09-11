import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { ChatSession, ChatSessionSchema } from '../schemas/chat-session.schema';
import { ChatSessionService } from '../services/chat-session.service';

@Module({
  imports: [
    MongooseModule.forRoot(
      process.env.MONGODB_URI || 
      'mongodb+srv://new_user_blya:2AKHOE1lpZYSoPru@cluster0.lgtepjy.mongodb.net/whatsapp_bankruptcy_bot?retryWrites=true&w=majority'
    ),
    MongooseModule.forFeature([
      { name: ChatSession.name, schema: ChatSessionSchema }
    ])
  ],
  providers: [ChatSessionService],
  exports: [ChatSessionService]
})
export class DatabaseModule {}