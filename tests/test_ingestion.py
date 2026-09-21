"""Tests for packet/flow ingestion robustness (segments the CSV-upload fix)."""

from pathlib import Path

from netwatch.ingestion.parser import load_flow_csv, normalize_packet_dict


def _write_csv(tmp_path: Path, content: str, name: str = "flow.csv") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_csv_with_non_numeric_numeric_columns(tmp_path):
    p = _write_csv(tmp_path, (
        "timestamp,src_ip,dst_ip,src_port,dst_port,bytes,packets\n"
        "2026-09-01T00:00:00Z,1.1.1.1,2.2.2.2,N/A,N/A,1500,3\n"
    ))
    recs = load_flow_csv(p)
    assert len(recs) == 1
    assert recs[0].src_ip == "1.1.1.1"
    assert recs[0].bytes_sent == 1500
    assert recs[0].src_port == 0


def test_csv_utf16_and_bom_encodings(tmp_path):
    bom = tmp_path / "bom.csv"
    bom.write_bytes("\ufefftimestamp,src_ip,dst_ip\n2026-09-01T00:00:00Z,1.1.1.1,2.2.2.2\n".encode("utf-8"))
    assert len(load_flow_csv(bom)) == 1

    utf16 = tmp_path / "utf16.csv"
    utf16.write_bytes("timestamp,src_ip,dst_ip\n2026-09-01T00:00:00Z,1.1.1.1,2.2.2.2\n".encode("utf-16"))
    assert len(load_flow_csv(utf16)) == 1


def test_csv_delimiters(tmp_path):
    semicolon = _write_csv(tmp_path, (
        "timestamp;src_ip;dst_ip;src_port\n2026-09-01T00:00:00Z;1.1.1.1;2.2.2.2;80\n"
    ), "semi.csv")
    recs = load_flow_csv(semicolon)
    assert len(recs) == 1
    assert recs[0].src_port == 80

    tab = _write_csv(tmp_path, (
        "timestamp\tsrc_ip\tdst_ip\tsrc_port\n2026-09-01T00:00:00Z\t1.1.1.1\t2.2.2.2\t443\n"
    ), "tab.csv")
    recs = load_flow_csv(tab)
    assert len(recs) == 1
    assert recs[0].src_port == 443


def test_csv_blank_rows_skipped(tmp_path):
    p = _write_csv(tmp_path, (
        "timestamp,src_ip,dst_ip\n2026-09-01T00:00:00Z,1.1.1.1,2.2.2.2\n,\n\n,3.3.3.3,4.4.4.4\n"
    ))
    assert len(load_flow_csv(p)) == 2


def test_normalize_packet_dict_never_drops_bad_numbers():
    rec = normalize_packet_dict({
        "timestamp": "t", "src_ip": "1.1.1.1", "dst_ip": "2.2.2.2",
        "src_port": "abc", "bytes": "1,500", "packets": "None",
    })
    assert rec is not None
    assert rec.src_port == 0
    assert rec.packets == 1
