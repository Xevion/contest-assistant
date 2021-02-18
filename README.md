# contest-assistant

A somewhat simple but feature concentrated bot to automate photography contests.

## Setup

```
git clone git@github.com:Xevion/contest-assistant.git
cd ./contest-assistant/
# Create a virtual environment if necessary
pip install -r requirements.txt
python main.py
```

## Commands

Default prefix is `$` or by mentioning the bot. Change it with the `prefix` command.

```
    advance [duration] [pingback = True]     
        Advance the state of the current period pertaining to this Guild.
    close
        Closes the current period.
    leaderboard
        Prints a leaderboard
    prefix <new_prefix>
        Changes the bot's saved prefix.
    status
        Provides the bot's current state in relation to internal config...
    submission <channel>
        Changes the bot's saved submission channel.
```

## Features

- [X] Customizable prefix
    - [X] Ensure 1-2 char length
    - [ ] Ensure ASCII
- [X] Adds upvote reactions automatically to the designated submissions channel
- [X] Removes regular messages
    - [ ] Remove Videos or Gifs
    - [X] Regular Messages
- [X] Deletes user's previous submissions if they upload more than one per period.
    - [X] Only tracks submissions per period - previous periods are ignored.
- [ ] Removes user's previous reactions if they vote more than once.
- [X] Ignore/remove reactions added to non-submission message in the channel (preserve)
- [ ] Calculates the winners automatically.
- [X] Handles submission removal
- [ ] Automatically switches between periods if a duration is specified
