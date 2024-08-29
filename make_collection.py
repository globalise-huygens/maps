import os
import json
import iiif_prezi3

iiif_prezi3.config.configs["helpers.auto_fields.AutoLang"].auto_lang = "en"

PREFIX = "https://data.globalise.huygens.knaw.nl/manifests/maps/"


def main(folder="maps"):

    collection = iiif_prezi3.Collection(
        id=f"{PREFIX}collection.json",
        label="Overview of map collections",
    )

    # for json file in 'maps' folder
    for f in os.listdir(folder):

        if not f.endswith(".json"):
            continue

        file_path = os.path.join(folder, f)

        with open(file_path) as infile:
            c = json.load(infile)

        c_id = c["id"]
        c_type = c["type"]
        c_label = c["label"]["en"][0]

        collection.add_item(
            iiif_prezi3.Reference(
                id=c_id,
                label=c_label,
                type=c_type,
            )
        )

    with open(os.path.join(folder, "collection.json"), "w") as outfile:
        outfile.write(collection.json(indent=2))


if __name__ == "__main__":
    main()
