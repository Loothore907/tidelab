"""One approved RSI private experiment; no arbitrary registry, date or market flags."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tidelab.rsi_private import initialize, prepare, execute
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('action',choices=['initialize','prepare','run'])
parser.add_argument('--terms-reviewed-utc-date',required=True)
args=parser.parse_args()
result={'initialize':initialize,'prepare':prepare,'run':execute}[args.action](args.terms_reviewed_utc_date)
print(json.dumps(result or {'status':'initialized'}))
