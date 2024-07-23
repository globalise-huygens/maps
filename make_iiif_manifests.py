import json
import os
from dataclasses import dataclass, field
from itertools import count
from unidecode import unidecode

import iiif_prezi3
import requests
from lxml import etree as ET

iiif_prezi3.config.configs["helpers.auto_fields.AutoLang"].auto_lang = "en"


@dataclass(kw_only=True)
class Base:
    code: str
    title: str


@dataclass(kw_only=True)
class Collection(Base):
    hasPart: list = field(default_factory=list)
    uri: str = field(default_factory=str)

    def files(self, use_filegroup=False):
        """
        For each file in the collection, yield the file or filegroup.

        Method that allows to iterate over all files in a collection,
        including files in sub-collections. If use_filegroup is True,
        filegroups are yielded as the last level, otherwise its
        individual files are yielded.

        The use_filegroup option is useful for collections that have
        combined multiple elements or inventory numbers in a meaningful
        collection (e.g. multiple sheets of a map) that need to be
        preserved as a whole in one single IIIF manifest.

        Args:
            use_filegroup (bool, optional): Yield filegrp as last level.
            Defaults to False.

        Yields:
            Iterator[File, FileGroup]: Iterator of File or FileGroup
        """
        for i in self.hasPart:
            if use_filegroup and isinstance(i, FileGroup):
                yield i
            elif isinstance(i, File):
                yield i
            else:
                yield from i.files(use_filegroup=use_filegroup)


@dataclass(kw_only=True)
class Fonds(Collection):
    pass


@dataclass(kw_only=True)
class Series(Collection):
    pass


@dataclass(kw_only=True)
class FileGroup(Collection):
    date: str


@dataclass(kw_only=True)
class File(Base):
    uri: str
    date: str
    metsid: str


def normalize_id(s: str) -> str:
    """
    Normalize an identifier so that it can be used in a URI.

    This function replaces white spaces, apostrophes, slashes
    and colons with a dash. It also removes all non-alphanumeric
    characters except for a dot and a dash.

    Args:
        s (str): Identifier to normalize.

    Returns:
        str: Normalized identifier.

    >>> normalize_id("7.27A, 7.37A")
    '7.27A-7.37A'
    """
    s = s.replace(" ", "-")
    s = s.replace("'", "-")
    s = s.replace("/", "-")
    s = s.replace(":", "-")

    s = "".join([c for c in s if c.isalnum() or c in "-."])

    while "--" in s:
        s = s.replace("--", "-")

    return s


def normalize_title(s: str) -> str:
    """
    Normalize a title so that it can be used in a URI.

    This function can be used when no identifier is available.
    It substitutes any diacritics in a title and converts it
    to lowercase. The same normalization as in normalize_id
    is applied.

    Args:
        s (str): Title to normalize.

    Returns:
        str: Normalized title.

    >>> normalize_title("Condé-sur-l'Escaut")
    'conde-sur-l-escaut'
    """
    s = normalize_id(s)

    s = unidecode(s).lower().strip()

    return s


def to_collection(
    i: Fonds | Series | FileGroup,
    base_url: str,
    target_dir: str,
    prefix="",
    base_url_manifests="",
    use_filegroup: bool = False,
):
    collection_filename = f"{prefix}{i.code}.json"
    collection_id = base_url + collection_filename

    dirname = os.path.dirname(collection_filename)

    collection = iiif_prezi3.Collection(id=collection_id, label=f"{i.code} - {i.title}")

    metadata = [
        iiif_prezi3.KeyValueString(
            label="Identifier",
            value={"en": [i.code]},
        ),
        iiif_prezi3.KeyValueString(
            label="Title",
            value={"en": [i.title]},
        ),
    ]

    if i.uri:
        metadata.append(
            iiif_prezi3.KeyValueString(
                label="Permalink",
                value={"en": [f'<a href="{i.uri}">{i.uri}</a>']},
            )
        )

    at_least_one_file = False
    for c in i.hasPart:
        if isinstance(c, Series):
            sub_part = to_collection(
                c,
                base_url,
                target_dir,
                prefix=collection_filename.replace(".json", "/"),
                base_url_manifests=base_url_manifests,
                use_filegroup=use_filegroup,
            )

        elif isinstance(c, FileGroup):
            if use_filegroup:
                sub_part = to_manifest(
                    c,
                    base_url_manifests,
                    target_dir,
                    prefix=collection_filename.replace(".json", "/"),
                )
            else:
                sub_part = to_collection(
                    c,
                    base_url,
                    target_dir,
                    prefix=collection_filename.replace(".json", "/"),
                    base_url_manifests=base_url_manifests,
                    use_filegroup=use_filegroup,
                )

        elif isinstance(c, File):
            if base_url_manifests:
                sub_part = to_manifest(
                    c,
                    base_url_manifests,
                    target_dir,
                    prefix=collection_filename.replace(".json", "/"),
                )
            else:
                sub_part = to_manifest(
                    c,
                    base_url,
                    target_dir,
                    prefix=collection_filename.replace(".json", "/"),
                )

        # Recursively add sub-collections and manifests if there is at least one file
        if sub_part:
            at_least_one_file = True
            collection.add_item(sub_part)

    if at_least_one_file:
        if dirname:
            os.makedirs(os.path.join(target_dir, dirname), exist_ok=True)

        with open(os.path.join(target_dir, collection_filename), "w") as outfile:
            outfile.write(collection.json(indent=2))

        return collection
    else:
        return None


def to_manifest(
    i: File | FileGroup,
    base_url: str,
    target_dir,
    prefix="",
    license_uri="https://creativecommons.org/publicdomain/mark/1.0/",
):
    print("Making manifest for", i.__class__.__name__, i.code)

    manifest_filename = f"{prefix}{i.code}.json"
    manifest_id = base_url + manifest_filename

    # If file already exists, skip
    if os.path.exists(manifest_filename):
        # return Reference (shallow) only
        return iiif_prezi3.Reference(
            id=manifest_id,
            label=f"{i.code} - {i.title}",
            type="Manifest",
        )

    manifest = iiif_prezi3.Manifest(
        id=manifest_id,
        label=[
            f"{i.code} - {i.title}",
        ],
        metadata=[
            iiif_prezi3.KeyValueString(
                label="Identifier",
                value={"en": [i.code]},
            ),
            iiif_prezi3.KeyValueString(
                label="Title",
                value={"en": [i.title]},
            ),
            iiif_prezi3.KeyValueString(
                label="Date",
                value={"en": [i.date or "?"]},
            ),
            iiif_prezi3.KeyValueString(
                label="Permalink",
                value={"en": [f'<a href="{i.uri}">{i.uri}</a>']},
            ),
        ],
        # seeAlso={"id": i.uri, "label": "Permalink"},
        rights=license_uri,
    )

    ranges = []  # {"scans": [], "metadata": [], "code": "", "title": ""}

    # Get scan-URIs from GAF
    if isinstance(i, FileGroup):
        for f in i.files(use_filegroup=True):
            # Is it a filegrp with filegrps? Then we need a range
            if isinstance(f, FileGroup):
                range_code = f.code
                range_title = f.title

                scans = []
                metadata = []

                for f2 in f.files():
                    new_scans = get_scans(f2.metsid)
                    scans += new_scans
                    metadata += [
                        [
                            iiif_prezi3.KeyValueString(
                                label="Identifier",
                                value={"en": [f2.code]},
                            ),
                            iiif_prezi3.KeyValueString(
                                label="Title",
                                value={"en": [f2.title]},
                            ),
                            iiif_prezi3.KeyValueString(
                                label="Date",
                                value={"en": [f2.date or "?"]},
                            ),
                            iiif_prezi3.KeyValueString(
                                label="Permalink",
                                value={"en": [f'<a href="{f2.uri}">{f2.uri}</a>']},
                            ),
                        ]
                        for _ in new_scans
                    ]

                if scans:
                    ranges.append(
                        {
                            "scans": scans,
                            "metadata": metadata,
                            "code": range_code,
                            "title": range_title,
                        }
                    )

            else:
                scans = get_scans(f.metsid)
                metadata = [
                    [
                        iiif_prezi3.KeyValueString(
                            label="Identifier",
                            value={"en": [f.code]},
                        ),
                        iiif_prezi3.KeyValueString(
                            label="Title",
                            value={"en": [f.title]},
                        ),
                        iiif_prezi3.KeyValueString(
                            label="Date",
                            value={"en": [f.date or "?"]},
                        ),
                        iiif_prezi3.KeyValueString(
                            label="Permalink",
                            value={"en": [f'<a href="{f.uri}">{f.uri}</a>']},
                        ),
                    ]
                    for _ in scans
                ]

                if scans:
                    ranges.append(
                        {
                            "scans": scans,
                            "metadata": metadata,
                            "code": f.code,
                            "title": f.title,
                        }
                    )

    else:
        scans = get_scans(i.metsid)
        metadata = [[] for _ in scans]

        if scans:
            ranges.append(
                {
                    "scans": scans,
                    "metadata": metadata,
                    "code": "",  # Structure not needed here
                    "title": "",
                }
            )

    canvas_counter = count(1)
    for nr, r in enumerate(ranges, 1):
        if r["code"]:
            make_range = True

            range = manifest.make_range(
                id=f"{manifest_id}/range/r{nr}",
                label=f"{r['code']} - {r['title']}",
            )
        else:
            make_range = False

        # Add scans
        for (file_name, iiif_service_info), metadata in zip(r["scans"], r["metadata"]):
            if file_name.endswith((".tif", ".tiff", ".jpg", ".jpeg")):
                base_file_name = file_name.rsplit(".", 1)[0]
            else:
                base_file_name = file_name

            n = next(canvas_counter)
            canvas_id = f"{manifest_id}/canvas/p{n}"

            print("Making canvas for", iiif_service_info)
            try:
                manifest.make_canvas_from_iiif(
                    url=iiif_service_info,
                    id=canvas_id,
                    label=base_file_name,
                    anno_id=f"{manifest_id}/canvas/p{n}/anno",
                    anno_page_id=f"{manifest_id}/canvas/p{n}/annotationpage",
                    metadata=metadata,
                )
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    print("404 error, skipping")

                    # Add placeholder canvas (empty)
                    manifest.make_canvas(
                        id=canvas_id,
                        label=base_file_name,
                        anno_id=f"{manifest_id}/canvas/p{n}/anno",
                        anno_page_id=f"{manifest_id}/canvas/p{n}/annotationpage",
                        metadata=metadata,
                    )
                elif e.response.status_code == 500:
                    print("500 error, skipping")

                    # Add placeholder canvas (empty)
                    manifest.make_canvas(
                        id=canvas_id,
                        label=base_file_name,
                        anno_id=f"{manifest_id}/canvas/p{n}/anno",
                        anno_page_id=f"{manifest_id}/canvas/p{n}/annotationpage",
                        metadata=metadata,
                    )
                else:
                    raise e

            if make_range:
                range.add_item(
                    iiif_prezi3.Reference(
                        id=canvas_id,
                        type="Canvas",
                    )
                )  # shallow only

    if next(canvas_counter) == 1:
        return  # empty manifests are not useful

    os.makedirs(
        os.path.join(target_dir, os.path.dirname(manifest_filename)), exist_ok=True
    )
    with open(os.path.join(target_dir, manifest_filename), "w") as outfile:
        outfile.write(manifest.json(indent=2))

    return manifest


def get_scans(metsid: str, cache_path="data/cache/") -> list[tuple[str, str]]:
    NS = {"mets": "http://www.loc.gov/METS/"}

    scans = []

    if metsid:
        if cache_path and metsid + ".xml" in os.listdir(cache_path):
            mets = ET.parse(os.path.join(cache_path, metsid + ".xml"))
        else:
            url = "https://service.archief.nl/gaf/api/mets/v1/" + metsid
            xml = requests.get(url).text
            mets = ET.fromstring(bytes(xml, encoding="utf-8"))

            if cache_path:
                with open(os.path.join(cache_path, metsid + ".xml"), "w") as outfile:
                    outfile.write(xml)

        for file_el in mets.findall(
            "mets:fileSec/mets:fileGrp[@USE='DISPLAY']/mets:file",
            namespaces=NS,
        ):
            file_id = file_el.attrib["ID"][:-3]  # without IIP
            service_info_url = file_el.find(
                "./mets:FLocat[@LOCTYPE='URL']",
                namespaces=NS,
            ).attrib["{http://www.w3.org/1999/xlink}href"]

            service_info_url = service_info_url.replace("/iip/", "/iipsrv?IIIF=/")

            file_name = (
                mets.find(
                    "mets:structMap/mets:div/mets:div[@ID='" + file_id + "']",
                    namespaces=NS,
                )
                .attrib["LABEL"]
                .split("/")[-1]
            )

            scans.append((file_name, service_info_url))

    return scans


def parse_ead(ead_file_path: str, filter_codes: set = set()) -> Fonds:
    tree = ET.parse(ead_file_path)

    fonds_code = tree.find("eadheader/eadid").text
    fonds_title = tree.find("eadheader/filedesc/titlestmt/titleproper").text
    permalink = tree.find("eadheader/eadid[@url]").attrib["url"]

    fonds = Fonds(
        code=fonds_code,
        title=fonds_title,
        uri=permalink,
    )

    series_els = tree.findall(".//c[@level='series']")
    subseries_els = tree.findall(".//dsc[@type='combined']/c[@level='subseries']")
    dsc_el = tree.find(".//dsc[@type='combined']")
    if series_els:
        for series_el in series_els:
            s = get_series(series_el, filter_codes=filter_codes)
            fonds.hasPart.append(s)
    elif subseries_els:
        for subseries_el in subseries_els:
            s = get_series(subseries_el, filter_codes=filter_codes)
            fonds.hasPart.append(s)
    elif dsc_el is not None:
        parts = get_file_and_filegrp_els(dsc_el, filter_codes=filter_codes)
        fonds.hasPart += parts

    return fonds


def get_series(series_el, filter_codes: set = set()) -> Series:
    series_code_el = series_el.find("did/unitid[@type='series_code']")
    series_title = "".join(series_el.find("did/unittitle").itertext()).strip()

    while "  " in series_title:  # double space
        series_title = series_title.replace("  ", " ")

    if series_code_el is not None:
        series_code = normalize_id(series_code_el.text)
    else:
        series_code = normalize_title(series_title)

    s = Series(code=series_code, title=series_title)

    parts = get_file_and_filegrp_els(series_el, filter_codes=filter_codes)
    s.hasPart += parts

    return s


def get_file_and_filegrp_els(series_el, filter_codes: set = set()):
    parts = []

    file_and_filegrp_els = series_el.xpath("child::*")
    for el in file_and_filegrp_els:
        if el.get("level") == "file":
            i = get_file(el, filter_codes)

        elif el.get("otherlevel") == "filegrp":
            i = get_filegrp(el, filter_codes)

        elif el.get("level") == "subseries":
            i = get_series(el, filter_codes)
        else:
            continue

        if i:
            parts.append(i)

    return parts


def get_filegrp(filegrp_el, filter_codes: set = set()) -> FileGroup:
    filegrp_code = normalize_id(filegrp_el.find("did/unitid").text)

    # Title
    filegrp_title = "".join(filegrp_el.find("did/unittitle").itertext()).strip()
    while "  " in filegrp_title:  # double space
        filegrp_title = filegrp_title.replace("  ", " ")

    if filegrp_code == "div.nrs.":
        filegrp_code += normalize_title(filegrp_title)

    # Date
    date_el = filegrp_el.find("did/unitdate")
    if date_el is not None:
        date = date_el.attrib.get("normal", date_el.attrib.get("text"))
    else:
        date = ""

    filegrp = FileGroup(
        code=filegrp_code,
        title=filegrp_title,
        date=date,
    )

    parts = get_file_and_filegrp_els(filegrp_el, filter_codes=filter_codes)
    filegrp.hasPart += parts

    return filegrp


def get_file(file_el, filter_codes: set = set()) -> File | None:
    did = file_el.find("did")

    # Inventory number
    inventorynumber_el = did.xpath("unitid[@identifier or @type='BD']")
    if inventorynumber_el:
        inventorynumber = inventorynumber_el[0].text
    else:
        return None

    # Filter on selection
    if filter_codes and inventorynumber not in filter_codes:
        return None

    # URI
    permalink = did.find("unitid[@type='handle']").text

    # Title
    title = "".join(did.find("unittitle").itertext()).strip()
    while "  " in title:  # double space
        title = title.replace("  ", " ")

    # Date
    date_el = did.find("unitdate")
    if date_el is not None:
        date = date_el.attrib.get("normal", date_el.attrib.get("text"))
    else:
        date = ""

    # METS id
    metsid_el = did.find("dao")
    if metsid_el is not None:
        metsid = metsid_el.attrib["href"].split("/")[-1]
    else:
        metsid = ""

    f = File(
        code=inventorynumber,
        title=title,
        uri=permalink,
        date=date,
        metsid=metsid,
    )

    return f


def main(
    ead_file_path: str,
    base_url_collections: str = "https://example.org/",
    base_url_manifests: str = "https://example.org/",
    filter_codes_path: str = "",
    use_filegroup: bool = False,
    target_dir: str = "iiif/",
) -> None:
    """
    Generate IIIF Collections and Manifests from an EAD file.

    Args:
        ead_file_path (str): Path to the EAD file.
        base_url (str): Base URL for the manifests.
        filter_codes_path (str, optional): Path to a JSON file with a list of inventory numbers to include. Defaults to "".
        hwd_data_path (str, optional): Path to a JSON file with the height and width of each scan. Defaults to "".

    Returns:
        None
    """

    # Restrict to a selection of inventory numbers
    if filter_codes_path:
        with open(filter_codes_path, "r") as infile:
            code_selection = set(json.load(infile))
    else:
        code_selection = []

    # Parse EAD, filter on relevant inventory numbers
    fonds = parse_ead(ead_file_path, filter_codes=code_selection)

    # Generate IIIF Collections and Manifests from hierarchy
    to_collection(
        fonds,
        base_url_collections,
        target_dir,
        base_url_manifests=base_url_manifests,
        use_filegroup=use_filegroup,
    )


if __name__ == "__main__":
    # Inventories

    for path in [
        # data/NA/ead/4.AANW.xml data/NA/ead/4.AKF.xml data/NA/ead/4.BRF.xml data/NA/ead/4.JSF.xml data/NA/ead/4.MCAL.xml
        "data/NA/ead/4.VEL.xml"
    ]:

        main(
            ead_file_path=path,
            base_url_manifests="https://data.globalise.huygens.knaw.nl/manifests/maps/",
            base_url_collections="https://data.globalise.huygens.knaw.nl/manifests/maps/",
            target_dir="maps/",
            use_filegroup=True,
        )
