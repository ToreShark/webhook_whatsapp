import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    logger: ['log', 'error', 'warn'],
  });

  app.use((require('express')).json());

  const port = process.env.PORT || 3000;
  await app.listen(port);
  console.log(`\nListening on port ${port}\n`);
}
bootstrap();
