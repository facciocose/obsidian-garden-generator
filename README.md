# obsidian-garden-generator
Python script to create a digital garden using an Obsidian vault as input

The script is executable is called `obgage`

You need to create a `config.ini` file with the following content:

```
[DEFAULT]
BASE_DIR = /obsidian/vault/dir
START_PAGE = home
OUTPUT_DIR = output
STATIC_DIR = static
TEMPLATES_DIR = templates
```

This config opens `home.md` file in the Obsidian vault and starts creating output files in `output` directory.

You can create jinja2 templates in the templates directory. Obgage will compile SASS files in `static/sass` directory.