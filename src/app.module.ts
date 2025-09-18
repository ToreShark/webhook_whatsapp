import { Module } from '@nestjs/common';
import { ScheduleModule } from '@nestjs/schedule';
import { WebhookController } from './webhook.controller';
import { DatabaseModule } from './modules/database.module';

@Module({
  imports: [
    DatabaseModule,
    ScheduleModule.forRoot()
  ],
  controllers: [WebhookController],
})
export class AppModule {}
