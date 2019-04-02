# Quota migration tools

## Get all quotas

    ./quotas.py --os-cloud old-cloud get -o old_quotas.json

## Apply quotas to new environment

    ./quotas.py --os-cloud new-cloud apply old_quotas.json

## Compare quotas against a reference

Comparing quotas extracted using the `get` subcommand:

    ./quotas.py --os-cloud new-cloud compare --quotafile old_quotas.json reference.json

Comparing live quotas against a reference:

    ./quotas.py --os-cloud new-cloud compare reference.json
