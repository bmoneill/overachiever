<div align="center">
    <h1><b>Overachiever: A multi-platform achievement manager</b></h1>
    <img width="40%" src="https://oneill.sh/img/overachiever-home.png" alt="Home Page">
    <img width="40%" src="https://oneill.sh/img/overachiever-game.png" alt="Game page">
    <img width="40%" src="https://oneill.sh/img/overachiever-guides.png" alt="Guides page">
</div>

## Table of contents

- [Overview](#overview)
- [Features](#features)
- [Deploying](#deploying)
  - [Docker](#docker)
  - [Disabling User Registration](#disabling-user-registration)
- [XBox 360 Achievement Icons](#xbox-360-achievement-icons)
- [Bugs](#bugs)
- [License](#license)

## Overview

This is an achievement manager for Xbox and Steam users, utilizing
[Flask](https://flask.palletsprojects.com/en/stable/), the
[Steam Web API](https://steamcommunity.com/dev), and the
[OpenXBL API](https://xbl.io/). It is substantially faster than
the Xbox Android app.

## Features

- [x] Fast, simple UI
- [x] Steam support
- [x] Xbox support
- [x] Search bar, filtering
- [x] Comprehensive user profiles with linked accounts, etc
- [x] Easy deployment
- [x] User-contributed achievement guides
- [x] User showcase
- [ ] PlayStation support
- [ ] Achievement guide ranking
- [ ] User stats
- [ ] SSO support

## Deploying

```shell
pip install -r requirements.txt
cp .env.example .env
# paste OpenXBL, Steam API keys into .env
python -m src
```

### Docker

```shell
docker compose up --build
```

### Disabling User Registration

User registration is disabled by default to protect API rate limits.
To enable registration, change `ALLOW_REGISTRATION` to `true` in your
`.env` file.

## XBox 360 Achievement Icons

Unfortunately, I have found no easy way to grab XBox 360 achievement icons
through any third-party API. As a result, icons must be manually added using the
following steps:

1. Download the icon to `static/`
2. Run `./helpers/add_360_icon.py <db_path> <title_id> <achievement_id> <url>`

Title IDs and Achievement IDs can be figured out by running the following
query:

```shell
curl 'https://api.xbl.io/v2/achievements/x360/{target_user.xuid}/title/{title_id}' \
    --header 'X-Authorization: YOUR_API_KEY'
```

## Bugs

If you find a bug, submit an issue, PR, or email me with a description and/or patch.

## License

Copyright (c) 2026 Ben O'Neill <ben@oneill.sh>. This work is released under
the terms of the MIT License. See [LICENSE](LICENSE) for the license terms.
