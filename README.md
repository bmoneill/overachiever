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

To disable user registration (to prevent others from using your API requests),
do the following: TODO

## Bugs

## License
