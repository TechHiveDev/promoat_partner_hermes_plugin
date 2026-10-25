# Promoat for Hermes

## What this plugin does

Promoat turns a script into a finished vertical 9:16 marketing video fronted by a realistic AI presenter. This plugin lets you do that from Hermes, with your own Promoat account, in plain conversation.

With it, Hermes can:

- Create presenter characters from selfies or a text description.
- Pick a free studio voice or clone your own.
- Create talking-head or multi-scene videos from a script or your own audio.
- Show the credit price before spending, then track the job until the video is ready.
- Edit finished videos: redo a scene, rewrite lines, or replace the sound.
- Check your credit balance, job history and generated assets.

Credits are used only with your own `PROMOAT_KEY`. Get an account, credits and a key at https://platform.promoat.ai.

## Install

Pick one of the two options:

```bash
# From the Hermes plugin catalog
hermes plugins install promoat

# From the GitHub repository
hermes plugins install TechHiveDev/promoat_partner_hermes_plugin
```

Hermes asks for `PROMOAT_KEY` at install and stores it outside this package. Do not commit a key or paste it in chat.

## Check the folder before installing

```bash
hermes plugins doctor . --ci
hermes plugins validate .
python -m unittest test_tools.py
```
