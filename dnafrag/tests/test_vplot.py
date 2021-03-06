import os
import gzip
import json
import tempfile

import numpy as np

import dnafrag

TEST_DIR = tempfile.TemporaryDirectory()
TEST_DATA_DIR = os.path.join(TEST_DIR.name, "test-data")
TEST_BEDFILE = "test-data-bedfile.bed.gz"
TEST_CHROM_SIZES_FILE = "chrom_sizes.txt"

FRAGBED_FILE = os.path.join(TEST_DATA_DIR, TEST_BEDFILE)
GENOME_FILE = os.path.join(TEST_DATA_DIR, TEST_CHROM_SIZES_FILE)

TEST_CHROM_LENS = [500, 1034, 2031, 60001]
MAX_INTERVAL_LEN = 400

NUM_TEST_CHROMS = len(TEST_CHROM_LENS)
TEST_CHROM_NAMES = ["chr{}".format(i) for i in range(NUM_TEST_CHROMS)]

bed_entries = None


def setup():
    global bed_entries
    bed_entries = {}
    if os.path.exists(TEST_DATA_DIR):
        os.system("rm -rf {}".format(TEST_DATA_DIR))
    os.mkdir(TEST_DATA_DIR)
    bed_lines = []
    for chrom_name, chrom_len in zip(TEST_CHROM_NAMES, TEST_CHROM_LENS):
        starts = np.random.randint(
            1, chrom_len - MAX_INTERVAL_LEN - 1, size=min(int(chrom_len / 10), 2001)
        )
        stops = starts + np.random.randint(
            2, MAX_INTERVAL_LEN + 1, size=starts.shape[0]
        )
        for start, stop in zip(starts, stops):
            bed_lines.append(str.encode("{}\t{}\t{}\n".format(chrom_name, start, stop)))
        bed_entries[chrom_name] = (starts, stops)
    with gzip.open(os.path.join(TEST_DATA_DIR, TEST_BEDFILE), "wb") as fp:
        for line in bed_lines:
            fp.write(line)
    with open(os.path.join(TEST_DATA_DIR, TEST_CHROM_SIZES_FILE), "w") as fp:
        for chrom_name, chrom_len in zip(TEST_CHROM_NAMES, TEST_CHROM_LENS):
            fp.write("{}\t{}\n".format(chrom_name, chrom_len))


def teardown():
    if os.path.exists(TEST_DATA_DIR):
        os.system("rm -rf {}".format(TEST_DATA_DIR))


def test_write_vplot(tmpdir):
    max_output_fraglen = 300
    output_dir = os.path.join(tmpdir, "output")

    dnafrag.core.write_fragbed(
        FRAGBED_FILE, output_dir, GENOME_FILE, max_output_fraglen
    )

    with open(os.path.join(output_dir, "metadata.json"), "r") as fp:
        metadata = json.load(fp)
    assert "file_shapes" in metadata
    chrom_sizes = metadata["file_shapes"]

    for chrom_idx in range(3):
        fname = os.path.join(output_dir, TEST_CHROM_NAMES[chrom_idx])
        assert os.path.exists(fname)
        a = dnafrag.core.load_sparse_array(fname)
        assert tuple(a.shape[::-1]) == tuple(chrom_sizes[TEST_CHROM_NAMES[chrom_idx]])


def test_vplot_data(tmpdir):
    output_dir = os.path.join(tmpdir, "output")
    dnafrag.core.write_fragbed(FRAGBED_FILE, output_dir, GENOME_FILE, MAX_INTERVAL_LEN)

    genome_data = dnafrag.load(output_dir)

    for chrom_name in ["chr0", "chr1", "chr2"]:
        a = dnafrag.core.load_sparse_array(os.path.join(output_dir, chrom_name))
        (starts, stops) = bed_entries[chrom_name]

        for start, stop in zip(starts, stops):
            midpoint = int((0.5 * (start + stop)))
            assert midpoint <= stop and midpoint >= start
            fraglen = stop - start - 1
            assert fraglen > 0 and fraglen <= MAX_INTERVAL_LEN

            assert a[midpoint, fraglen]["v"] > 0


def test_vplot_data_load_directory(tmpdir):
    output_dir = os.path.join(tmpdir, "output")
    dnafrag.core.write_fragbed(FRAGBED_FILE, output_dir, GENOME_FILE, MAX_INTERVAL_LEN)

    genome_data = dnafrag.load(output_dir)

    for chrom_name in ["chr0", "chr1", "chr2"]:
        a = dnafrag.core.load_sparse_array(os.path.join(output_dir, chrom_name))
        (starts, stops) = bed_entries[chrom_name]

        for start, stop in zip(starts, stops):
            midpoint = int((0.5 * (start + stop)))
            assert midpoint <= stop and midpoint >= start
            fraglen = stop - start - 1
            assert fraglen > 0 and fraglen <= MAX_INTERVAL_LEN

            assert genome_data[chrom_name][fraglen, midpoint]["v"] > 0


def test_exact_coords(tmpdir):

    fragbed = os.path.join(tmpdir, TEST_BEDFILE)
    with gzip.open(fragbed, "wb") as fp:
        fp.write(b"chr1\t100\t201\n")
        fp.write(b"chr1\t100\t201\n")
        fp.write(b"chr1\t500\t652\n")

    chrszs = os.path.join(tmpdir, TEST_CHROM_SIZES_FILE)
    with open(chrszs, "w") as fp:
        fp.write("chr1\t1000\n")

    output_dir = os.path.join(tmpdir, "output")
    dnafrag.core.write_fragbed(fragbed, output_dir, chrszs, MAX_INTERVAL_LEN)

    data = dnafrag.load(output_dir)["chr1"]

    assert data[100, 150]["v"] == 2
    assert data[151, 576]["v"] == 1


def test_exact_coords_array_access(tmpdir):

    fragbed = os.path.join(tmpdir, TEST_BEDFILE)
    with gzip.open(fragbed, "wb") as fp:
        fp.write(b"chr1\t100\t201\n")
        fp.write(b"chr1\t100\t201\n")
        fp.write(b"chr1\t500\t652\n")

    chrszs = os.path.join(tmpdir, TEST_CHROM_SIZES_FILE)
    with open(chrszs, "w") as fp:
        fp.write("chr1\t1000\n")

    output_dir = os.path.join(tmpdir, "output")
    dnafrag.core.write_fragbed(fragbed, output_dir, chrszs, MAX_INTERVAL_LEN)

    data = dnafrag.load(output_dir)["chr1"]

    A = np.zeros((MAX_INTERVAL_LEN, 100), dtype=np.int32)

    data.fill_array(0, A, zero=False)
    assert A.sum() == 0

    data.fill_array(0, A, zero=True)
    assert A.sum() == 0

    data.fill_array(1, A, zero=True)
    assert A.sum() == 0

    data.fill_array(100, A, zero=False)
    assert A.sum() == 2
    assert A[100, 50] == 2

    data.fill_array(101, A, zero=False)
    assert A.sum() == 4
    assert A[100, 50] == 2
    assert A[100, 49] == 2

    data.fill_array(101, A, zero=True)
    assert A.sum() == 2
    assert A[100, 49] == 2

    data.fill_array(101, A, zero=True)
    assert A.sum() == 2
    assert A[100, 49] == 2

    A = np.zeros((MAX_INTERVAL_LEN, 91), dtype=np.int32)

    data.fill_array(0, A, zero=False)
    assert A.sum() == 0

    data.fill_array(0, A, zero=True)
    assert A.sum() == 0

    data.fill_array(1, A, zero=True)
    assert A.sum() == 0

    data.fill_array(100, A, zero=False)
    assert A.sum() == 2
    assert A[100, 50] == 2

    data.fill_array(101, A, zero=False)
    assert A.sum() == 4
    assert A[100, 50] == 2
    assert A[100, 49] == 2

    data.fill_array(101, A, zero=True)
    assert A.sum() == 2
    assert A[100, 49] == 2

    data.fill_array(101, A, zero=True)
    assert A.sum() == 2
    assert A[100, 49] == 2


def test_tiledb_test():
    import tiledb

    n = 1000
    m = 1000
    num_vals = 1000

    n_idxs = np.sort(np.random.choice(n, num_vals, replace=False))
    m_idxs = np.sort(np.random.choice(m, num_vals, replace=False))
    values = np.random.randint(0, 100, num_vals, np.uint8)

    ctx = tiledb.Ctx()

    n_tile_extent = min(100, n)

    d1 = tiledb.Dim(
        "ndom", domain=(0, n - 1), tile=n_tile_extent, dtype="uint32", ctx=ctx
    )
    d2 = tiledb.Dim("mdom", domain=(0, m - 1), tile=m, dtype="uint32", ctx=ctx)

    domain = tiledb.Domain(d1, d2, ctx=ctx)

    v = tiledb.Attr(
        "v",
        filters=tiledb.FilterList([tiledb.LZ4Filter(level=-1)]),
        dtype="uint8",
        ctx=ctx,
    )

    schema = tiledb.ArraySchema(
        domain=domain,
        attrs=(v,),
        capacity=10000,
        cell_order="row-major",
        tile_order="row-major",
        sparse=True,
        ctx=ctx,
    )

    with tempfile.TemporaryDirectory() as tdir:

        path = os.path.join(tdir, "arr.tiledb")

        tiledb.SparseArray.create(path, schema)

        with tiledb.SparseArray(path, mode="w", ctx=ctx) as A:
            A[n_idxs, m_idxs] = values

        ctx2 = tiledb.Ctx()

        s = tiledb.SparseArray(path, mode="r", ctx=ctx2)
        vs1 = s[1:10, 1:50]

        _ = s[:, :]
        vs2 = s[1:10, 1:50]

        assert vs1["v"].shape[0] == vs2["v"].shape[0]
