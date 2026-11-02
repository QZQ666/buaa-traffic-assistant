"""Synthetic package expansion markup: no real account or usage data."""
import sys
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_app import parse_home, SessionExpired

headers = '<tr><th>产品名称</th><th>已用流量</th><th>免费流量剩余(不含套餐)</th><th>计费流量剩余(不含套餐)</th><th>套餐详情</th></tr>'
package = '<table><tr><th>套餐名称</th><th>统计</th></tr><tr><td>测试流量包</td><td>可用流量：99G</td></tr></table>'
row = '<tr><td>测试产品</td><td>12.500G</td><td>50G</td><td>8.250G</td><td>{}</td></tr>'

def legacy(html):
    soup = BeautifulSoup(html, 'html.parser')
    for table in soup.select('table'):
        rows = [[c.get_text(' ', strip=True) for c in r.select('th,td')] for r in table.select('tr')]
        for i, cells in enumerate(rows):
            if '已用流量' in cells:
                for vals in rows[i+1:]:
                    if len(vals) == len(cells):
                        return dict(zip(cells, vals))
    return None

# Server-side widget state: detail table lives inside the final product cell.
embedded = '<table><thead>' + headers + '</thead><tbody>' + row.format('<div hidden>' + package + '</div>') + '</tbody></table>'
assert legacy(embedded) is None, 'Fixture must reproduce the previous failure'
records = parse_home(embedded)
assert len(records) == 1
assert records[0]['计费流量剩余(不含套餐)'] == '8.250G'
assert '99G' not in ' '.join(records[0].values())
print('PASS: reproduces old nested-package failure and reads parent product correctly')

# After browser JS expansion: detail table lives in a sibling colspan row.
expanded = '<table>' + headers + row.format('收起') + '<tr><td colspan="5">' + package + '</td></tr></table>'
assert parse_home(expanded)[0]['已用流量'] == '12.500G'
assert len(parse_home(expanded)) == 1
plain = '<table>' + headers + row.format('展开') + '</table>'
assert parse_home(plain)[0]['已用流量'] == '12.500G'
print('PASS: expanded detail rows and accounts without packages still work')

assert records[0].packages[0]['套餐名称'] == '测试流量包'
assert records[0].packages[0]['可用流量'] == '99G'
assert len(parse_home(expanded)[0].packages) == 1
assert not parse_home(plain)[0].packages
full_package = '<table><tr><th>套餐名称</th><th>购买时间</th><th>有效期</th><th>统计</th></tr><tr><td>示例包A</td><td>2026-12-01</td><td>0天</td><td><button>总流量：30.000G</button><button>可用流量：18.500G</button><button>61%</button></td></tr></table>'
multiple = '<table>' + headers + row.format(full_package) + row.format(package) + '</table>'
products = parse_home(multiple)
assert len(products) == 2
assert products[0].packages[0]['总流量'] == '30.000G'
assert products[0].packages[0]['可用流量'] == '18.500G'
assert products[0].packages[0]['购买时间'] == '2026-12-01'
assert products[0].packages[0]['有效期'] == '0天'
assert products[1].packages[0]['套餐名称'] == '测试流量包'
assert len(products[1].packages) == 1
print('PASS: package statistics, literal validity and correct association to each product')

try:
    parse_home('<input id="loginform-password">')
except SessionExpired:
    pass
else:
    raise AssertionError('Login page must not be mistaken for product data')
print('PASS: expired login remains distinguishable from missing product data')
