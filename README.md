# DotaBot

DotaBot is a simple Discord bot for organizing Dota 2 games within a community. It helps players organize queues, get daily rewards, and start matches faster.

## Invite Link
Use this link to add the bot to your server: [Install Link](https://discord.com/oauth2/authorize?client_id=1336990172767846501)

## Features
- **Queue System**  
  Commands to start different queue types:
  - `!queue (!q)` - Unranked queue  
  - `!ranked (!r)` - Ranked queue  
  - `!turbo (!t)` - Turbo queue  
  - `!battlecup (!bc)` - Battle Cup queue  
  - `!inhouse (!ih)` - Inhouse queue  

- **Currency System**  
  - `!daily (!d)` - Claim a daily reward  
  - `!mmr` - Check your current points  
  - `!top` - View top point and streak holders  

- **Role Management**  
  - `!role` - Gives you the `queue` role  

## Installation
1. Clone or download this repository.
2. Install dependencies:
   ```bash
   pip install -U discord.py
   ```
3. Set the bot token as an environment variable (`DOTABOT_APP_ID`).
4. Run the bot:
   ```bash
   python bot.py
   ```
