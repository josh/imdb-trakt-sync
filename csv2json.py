#!/usr/bin/env python3

import csv
import json
import sys

data = [dict(r) for r in csv.DictReader(sys.stdin)]
json.dump(data, sys.stdout, ensure_ascii=False)
