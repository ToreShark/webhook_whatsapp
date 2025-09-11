import { Module } from '@nestjs/common';
import { WebhookController } from './webhook.controller';
import { DatabaseModule } from './modules/database.module';

@Module({
  imports: [DatabaseModule],
  controllers: [WebhookController],
})
export class AppModule {}
