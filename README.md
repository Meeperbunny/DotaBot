# Dota Queue Bot

A Discord bot for organizing Dota queues, daily MMR rewards, and trivia games.  
It uses a **CSV** file to store user MMR, and **heroStats.json** data for hero info.  
The bot includes multiple commands for starting queues, checking MMR, showing top MMR holders,  
and running two types of trivia:  
- **Match Trivia** (Radiant vs. Dire, guess winner)  
- **Hero Stats Over/Under** (guess if hero stat is higher or lower than shown)  

## Quick Features

- **Daily**: `!D`, `!daily`, `!d` - claim a daily 25 MMR reward, once every 23 hours.
- **Queues**: `!Q`, `!R`, `!IH`, etc. - start Dota queues and mention roles.
- **Trivia**: `!trivia` - 50% chance for Match Trivia, 50% for Hero Stats Over/Under.  
  - Double down (±10 MMR) or normal (±5 MMR).
- **MMR**: `!mmr` / `!MMR` - check how much MMR you have; `!top` / `!topmmr` - see top MMR holders.

## How to Run

1. **Set Up**  
   - Clone the repo or copy the files.
   - Install requirements (e.g. `discord.py`, `requests`).

2. **Token**  
   - The bot reads your token from the environment variable `DISCORD_BOT_TOKEN`.
   - Alternatively, replace `"YOUR_BOT_TOKEN_HERE"` in the code with your real token (not recommended for public repos).

3. **heroStats.json**  
   - If `heroStats.json` isn’t found locally or in the temp folder, it fetches from the OpenDota API.

4. **Run**  
   ```bash
   python bot.py
