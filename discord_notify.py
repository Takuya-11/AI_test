import os
import sys
import asyncio
import discord
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MESSAGE = '🤖 Discord Botからの自動通知です！'


def get_env():
    token = os.getenv('DISCORD_BOT_TOKEN', '')
    channel_id = os.getenv('DISCORD_CHANNEL_ID', '')

    if not token or token == 'ここにBot Tokenを入れる':
        print('エラー: .env に DISCORD_BOT_TOKEN が設定されていません。')
        sys.exit(1)
    if not channel_id or channel_id == 'ここにチャンネルIDを入れる':
        print('エラー: .env に DISCORD_CHANNEL_ID が設定されていません。')
        sys.exit(1)

    try:
        channel_id = int(channel_id)
    except ValueError:
        print('エラー: DISCORD_CHANNEL_ID は数値で設定してください。')
        sys.exit(1)

    return token, channel_id


async def send_message(token, channel_id, message):
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    result = {'success': False}

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(channel_id)

            if channel is None:
                print(f'エラー: チャンネルID {channel_id} が見つかりません。')
                print('  → BotがサーバーにいるかDiscord Developer PortalでMessage Content Intentを確認してください。')
                await client.close()
                return

            await channel.send(message)

            print('=' * 30)
            print('Discord通知に成功しました！')
            print('=' * 30)
            print(f'チャンネル：#{channel.name}')
            print(f'メッセージ：{message}')
            result['success'] = True

        except discord.Forbidden:
            print('エラー: Botにメッセージ送信権限がありません。')
            print('  → Discordサーバーでチャンネルの権限設定を確認してください。')
        except discord.HTTPException as e:
            print(f'エラー: メッセージ送信に失敗しました。\n詳細: {e}')
        finally:
            await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure:
        print('エラー: Bot Tokenが無効です。DISCORD_BOT_TOKEN を確認してください。')
        sys.exit(1)
    except discord.ConnectionClosed:
        print('エラー: Discordへの接続が切断されました。')
        sys.exit(1)
    except Exception as e:
        print(f'エラー: Discordへの接続に失敗しました。\n詳細: {e}')
        sys.exit(1)

    if not result['success']:
        sys.exit(1)


def main():
    token, channel_id = get_env()

    try:
        message = input(f'送信するメッセージを入力してください（空でEnterで既定のメッセージ）：').strip()
    except (KeyboardInterrupt, EOFError):
        print('\n中止しました。')
        sys.exit(0)

    if not message:
        message = DEFAULT_MESSAGE

    print(f'\nDiscordに送信中...\n')
    asyncio.run(send_message(token, channel_id, message))


if __name__ == '__main__':
    main()
