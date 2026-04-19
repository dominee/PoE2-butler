# PoE2 Hideout Butler

*"Think of it as your personal PoE2 Hideout buttler who takes care of your gear and stash."*

**PoE2 Hideout Butler** is a SPA web application used by Path of Exile 2 (by GGG) players to view their game characters gear and inventory online. The web serves as an online snapshot of the users in game assests, allowing him to review items in stashes and provides additional information:
* Shows item details when clicked with mouse, similar to an ingame item details but in a side pane with additional information.
* Estimates the item current market price by fetching ( and caching) 3rd party APIs like [poe.ninja](https://poe.ninja) for the item specific stat (in a range within a minor tolerance).
* Highlight valuable items to serve as automated price-check of "Dump Stashtabs" while the player is offline.
* Creates links to [POE2 Trade Search](https://www.pathofexile.com/trade2/search/poe2/Fate%20of%20the%20Vaal) website to search for a item upgrade (sets item stats as minimal stat range in search, -5%)
Pairing with an PoE2 GGG accunt is required by the user, to access the needed data for his account. The user has to grant the Application access using OAuth2.
The goal is to obtain as much as possible additional information about an item and create possibilities to create actions with that item on another 3rd party services.

## Folder structure

This file as the original instruction context. I will also update it when providing additional or new context.
* `README.md` - Generic documentation for humans, according to best practices.
* `AGENTS.md` - Use this file to store your context, it will be used by you and other AI agents as a main source of context.
* `DEPLOY.md` - Use to describe the build and deploy process.
* `GGG_API.md` - Use to document GGG API OAuth2 related documentation and setup.
You are allowed to create subagent configuration or skills if required.

## Implementation instructions

As the context will probably be large, you are encouraged to create specialized subagents, skills or store partial domain specific context in the specific application component subfolder.
Focus on building using an iterative aproach starting form core features, building up one component at a time.
Verify larger changes by running tests.
If buiilding a large functional block you are allowed to commit building steps in a reasonable matter, after tests pass.

## Visual

The colour scheme and visual theme should be derived from [Path of Exile 2 Website](https://pathofexile2.com/home), but not direct copies.
Design should be flat and minimal, minimalizing menu sizes to provide maximum space for the application content itself.
Keep page load speed in mind.
The item details pane should be on the right side fo the screen and provide as much information as possible.

## Technical description

Security is paramount. Choose security over performance when presented with a choice.
The application is an SPA aplication with JSON only API.
Python3 is preferred, but not a mandatory option if far more suitable alternative exists.
Application stack should be fully dockerized and bundled by docker compose.
Admin interface is not part of the web application, should be a separate application.
Heavy use of frontend is encouraged, like to store filters or other user data.
Backend API should be as much read-only as possible, with minimum writing operation.
If possible GGG should serve as an identity provider, tehrefore users should sign in using GGG Oauth2.
If managing python `uv` is used for python virtual environment management.

### Discord bot

Later the application API will be used as a datasource for a Discord bot used to link items, search in stash, various statistics or actions as generating treade search links.
The discord bot will be developed in this workspace but as an separate repository later.


## Business description

User pairs their account / logs in using GGG OAuth2 , to access their GGG acounts data.
BE refreshes user data from GG api to obtain a fresh snapshot. This includes characters, character data, gear, stashes.
User is provided with a dashboard showcasing the (chosen) characters gear. Chracter can be changed.
Below it the content of stashtabs is shown, in a similar representation than original stashtabs.
Curency and other special stashtabs should be included in the view.
A Table list representation of items should be available as well.
Search function is available, to search items by name or type.
Filters are availabe to filter only specific items.
Clicking an item displays a item detail pane with information and possible actions with the item.
    - Search for that particular item (whith such stats) on PoEe Trade website. The stats should allow a 10% (configurable) parameter for stat spread.
    - Search for an upgrade (items whith same stats but higher values than current ones) on PoE2 Trade.
Price estimates are displayed as part as item details, but as part of item icons (or below) when listing items.
The item details for an item contain as much information as posssible, from GG, 3rd party APIs, their combination or derived from them.


## Docker

Application will de deployed via docker compose.
The target testing VM will be used to run the PROD and DEV stacks paralel, with access to them routed preferably by traefik via subdomains.
I will provide a domain later, but you can make some sugestions based on the knowledge of context and community.

## Deploy

In later stages the application will be deployed remotely as part of development and testing.
You will obtain ssh access to the VM for testing and troubleshooting, via a ssh key.
This are the parameters of the proposed VM (Digital Ocean Droplet).

```
Plan Type: Basic
CPU Option: Premium AMD
vCPU: 1
RAM: 1 GB
Disk: 25 GB
Bandwidth: 1000 GB
```