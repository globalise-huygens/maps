"""
Generate IIIF v2 manifests for usage in Recogito.
"""

import json
from iiif_prezi.factory import ManifestFactory
import requests

IIIF_BASE_URL = "https://service.archief.nl/iipsrv?IIIF="

# Define our Manifest factory
fac = ManifestFactory()
fac.set_base_prezi_uri("https://globalise-huygens.github.io/maps/manifests/v2/")
fac.set_base_image_uri(IIIF_BASE_URL)
# fac.set_base_prezi_dir("./")
fac.set_iiif_image_info(2.0, 2)  # Version, ComplianceLevel
# fac.set_debug("warn")

collections = [
    (
        "Taiwan",
        ["/home/leon/Documents/GLOBALISE/maps/maps/4.VEL/B/B.3/B.3.16.json"],
    ),
    (
        "China_Japan",
        ["/home/leon/Documents/GLOBALISE/maps/maps/4.VEL/B/B.3/B.3.10.json"],
    ),
    (
        "Indonesia",
        ["/home/leon/Documents/GLOBALISE/maps/maps/4.VEL/B/B.3/B.3.20/java.json"],
    ),
    (
        "India",
        [
            "/home/leon/Documents/GLOBALISE/maps/maps/4.VEL/B/B.3/B.3.2.json",
            "/home/leon/Documents/GLOBALISE/maps/maps/4.VEL/B/B.3/B.3.6.json",
        ],
    ),
]


def get_manifest_data(files):
    manifest_data = []

    for i in files:
        # r = requests.get(i)
        # data = r.json()
        with open(i) as f:
            data = json.load(f)

        for manifest in data["items"]:
            manifest_id = manifest["id"]
            label = manifest["label"]["en"][0].strip()

            with open(
                manifest_id.replace(
                    "https://data.globalise.huygens.knaw.nl/manifests/maps/",
                    "/home/leon/Documents/GLOBALISE/maps/maps/",
                )
            ) as f:
                manifest = json.load(f)

            metadata = manifest["metadata"]
            if metadata == []:
                metadata = data["metadata"]
            # Example [{'label': {'en': ['Identifier']}, 'value': {'en': ['234']}}, {'label': {'en': ['Title']}, 'value': {'en': ['1e exemplaar']}}, {'label': {'en': ['Date']}, 'value': {'en': ['?']}}, {'label': {'en': ['Permalink']}, 'value': {'en': ['<a href="http://hdl.handle.net/10648/27284337-5324-4daf-8125-2f97cfdd0be9">http://hdl.handle.net/10648/27284337-5324-4daf-8125-2f97cfdd0be9</a>']}}]

            metadata = {m["label"]["en"][0]: m["value"]["en"][0] for m in metadata}

            for canvas in manifest["items"]:
                canvas_id = canvas["id"]
                canvas_label = canvas["label"]["en"][0].strip()
                service = (
                    canvas["items"][0]["items"][0]["body"]["service"][0]["@id"]
                    + "/info.json"
                )

                manifest_data.append(
                    (label, metadata, service, canvas_id, canvas_label)
                )

    return manifest_data


def main():
    for name, files in collections:
        print(f"Processing {name}")
        manifest_data = get_manifest_data(files)

        # Create the manifest
        manifest = make_manifest_v2(manifest_data, name)

        # And save it
        with open(
            f"/home/leon/Documents/GLOBALISE/maps/static/manifests/v2/{name}.json", "w"
        ) as f:
            manifest_json = manifest.toJSON(top=True)
            manifest_json["@id"] = manifest_json["@id"].replace(
                "manifest.json", f"{name}.json"
            )

            json.dump(manifest_json, f, indent=4)


def make_manifest_v2(manifest_data, label):
    # Create the manifest itself with basic metadata
    manifest = fac.manifest(label=label)
    manifest.viewingDirection = "left-to-right"

    # And then the canvases in a sequence
    seq = manifest.sequence()

    for label, metadata, service, canvas_id, canvas_label in manifest_data:
        print(label)

        cvs = seq.canvas(
            ident=canvas_id,
            label=f"{canvas_label} - {label}",
        )

        print(service)
        cvs.set_image_annotation(
            imgid=service.replace("/info.json", "").replace(
                "https://service.archief.nl/iipsrv?IIIF=", ""
            ),
            iiif=True,
        )

        metadata = {"Label": canvas_label, **metadata}

        print(metadata)
        cvs.set_metadata(metadata)

    return manifest


if __name__ == "__main__":
    main()
