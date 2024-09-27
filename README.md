# GLOBALISE Early Modern Map Collection

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-blue.svg)](https://creativecommons.org/licenses/by/4.0/)

This repository is part of the [**GLOBALISE project**](https://globalise.huygens.knaw.nl/). It provides access to colonial-era map collections from the Dutch National Archive (and in future other heritage institutions). These collections include significant maps created during the 17th and 18th centuries, depicting regions under Dutch colonial influence.

The repository provides scripts to prepare maps for annotation by creating IIIF Manifests and Collections, enabling georeferencing, addition of transcriptions, and thus facilitating further research in the GLOBALISE project and beyond. Additionally, the repository includes pilot projects for automated enrichments of the maps. These are work in progress.

## Overview

The repository contains the following components:

### Map Collection

The map collection is a structured dataset of maps from the Dutch National Archive, compiled as IIIF Collections and IIIF Manifests (cf. [IIIF Presentation 3.0](https://iiif.io/api/presentation/3.0/)). The dataset is generated from the archive's EAD files (included in the `data/NA` folder). These can be generated with the `make_iiif_manifests.py` and `make_collection.py` scripts.

The files are not included in this repository due to their size. However, they can be found in the repository's data deposit on Zenodo. The files are also hosted by GLOBALISE:

- Collection of all collections: https://data.globalise.huygens.knaw.nl/manifests/maps/collection.json
- Mirador viewer of all collections: https://projectmirador.org/embed/?iiif-content=https://data.globalise.huygens.knaw.nl/manifests/maps/collection.json

### Enrichments

These are work in progress and include work on:

- Georeferencing
- Text spotting
- Transcription
- Image segmentation

### Other

Some static files are included in this repository. This includes a Mirador viewer for the map collection, which serves the GitHub pages: https://globalise-huygens.github.io/maps.

## License

The data is licensed under the Creative Commons Attribution 4.0 International License. A copy of the repository is available in Zenodo.
