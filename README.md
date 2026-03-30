<div align="center">
    <h1><b>Overachiever</b></h1>
    <h4>
        An Xbox Achievement Manager
    </h4>
</div>

## Table of contents

- [Overview](#overview)
- [Deploying](#deploying)
  - [Docker](#docker)
  - [Disabling User Registration](#disabling-user-registration)
- [Bugs](#bugs)
- [License](#license)

## Overview

This is a Flask achievement manager for Xbox users, utilizing the
[OpenXBL API](https://xbl.io/).

## Features

- [x] Fast, simple UI
- [x] Easy deployment
- [ ] Achievement guide support

## Deploying

```shell
pip install -r requirements.txt
cp .env.example .env
# paste OpenXBL API key into .env
flask run
```

### Docker

TODO

### Disabling User Registration

User registration is disabled by default to protect API rate limits.
To enable registration, change `ALLOW_REGISTRATION` to `true` in your
`.env` file.

## Bugs

If you find a bug, submit an issue, PR, or email me with a description and/or patch.

## License

Copyright (c) 2026 Ben O'Neill <ben@oneill.sh>. This work is released under
the terms of the MIT License. See [LICENSE](LICENSE) for the license terms.
