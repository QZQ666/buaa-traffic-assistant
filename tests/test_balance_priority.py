import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_app import ProductRecord, select_remaining, traffic_bytes

def record(free, packages, paid='8.250G'):
    return ProductRecord({'免费流量剩余(不含套餐)': free, '计费流量剩余(不含套餐)': paid},
                         [{'可用流量': available} for available in packages])

assert select_remaining(record('40G', ['20G']))[:2] == ('免费余量', '40G')
assert select_remaining(record('0byte', ['20G', '512MB']))[:2] == ('流量包可用量', '20.500 GB')
assert select_remaining(record('0GB', ['0G']))[:2] == ('付费余量', '8.250G')
assert select_remaining(record('0B', []))[:2] == ('付费余量', '8.250G')
assert select_remaining(record('0B', [], '0G'))[:2] == ('付费余量', '0G')
assert select_remaining(record('1byte', ['20G']))[:2] == ('免费余量', '1byte')
assert select_remaining(record('0B', ['1B']))[:2] == ('流量包可用量', '1 B')
assert select_remaining(record('—', ['20G']))[:2] == ('免费余量', '—')
assert select_remaining(record('0B', ['20G', '—']))[:2] == ('流量包可用量', '—')
assert traffic_bytes('1024 KiB') == traffic_bytes('1 MiB')
assert traffic_bytes('unlimited') is None
print('PASS: free, combined packages, paid fallback, byte precision and unknown-tier safety')
