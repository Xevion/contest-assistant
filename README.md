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

Default prefix is `$`, change it as you please.

```
$config prefix PREFIX
    Changes the prefix of the bot's commands.

$config submissions SUBMISSIONS_CHANNEL
    Changes the channel moderated for submissions.

$start submissions [DURATION = -1] [AUTOFORWARD = true]
    Starts the submissions period.

$start voting [DURATION = - 1]
    Starts the voting period.

$stop submissions
    Stops the submissions period.

$stop voting
    Stops the voting period.

$calculate
    Calculates and prints a scoreboard of all submissions with the submitting user and a link to their submission.
```

## Features

- [X] Customizable prefix
    - [X] Ensure 1-2 char length
    - [ ] Ensure ASCII
- [ ] Adds upvote reactions automatically to the designated submissions channel
- [ ] Removes regular messages and videos
- [ ] Deletes user's previous submissions if they upload more than one per period.
    - [ ] Only tracks submissions per period - previous periods are ignored.
- [ ] Removes user's previous reactions if they vote more than once.
- [ ] Calculates the winners automatically.
- [ ] Handles submission removal
- [ ] Automatically switches between periods if a duration is specified
