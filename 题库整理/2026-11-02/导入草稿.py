"""把已核对的纯文字题逐条送入现有题库草稿接口；默认只做本地检查。"""
from pathlib import Path
import argparse, json, urllib.request, urllib.error, getpass, sys

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='实际登录本地网站并建立草稿；不发布题目')
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    args=parser.parse_args()
    rows=[json.loads(line) for line in (ROOT/'现有接口纯文字草稿.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    for row in rows:
        content=row['content']
        assert 1<=content['sequence']<=999
        assert len(content['title'])<=150 and len(content['prompt'])<=6000
        for field in content['fields']:
            if field['kind']=='choice':assert field['expected'] in field['options']
            elif field['kind']=='multi':assert field['expected'] and set(field['expected'])<=set(field['options'])
            elif field['kind']=='cell':assert field['expected']
            else:raise ValueError('不支持的自动导入题型')
    print(f'本地格式检查通过：{len(rows)}道已核对纯文字客观题。')
    if not args.apply:
        print('尚未连接服务器或写入数据。需要导入时加 --apply；使用管理员账号登录，只建草稿。')
        return
    base=args.base_url.rstrip('/')
    # 本包仅支持本机服务，避免把管理员密码发往远程地址。
    if base not in ('http://127.0.0.1:8000','http://localhost:8000'):
        raise ValueError('请使用本机后端 http://127.0.0.1:8000 或 http://localhost:8000')
    def request(path,method='GET',body=None,token=None):
        data=None if body is None else json.dumps(body,ensure_ascii=False).encode('utf-8')
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=urllib.request.Request(base+path,data=data,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
        except urllib.error.HTTPError as e:
            detail=e.read().decode('utf-8',errors='replace')
            raise RuntimeError(f'后端返回HTTP {e.code}：{detail[:500]}') from None
    username=input('管理员用户名：').strip()
    password=getpass.getpass('管理员密码（不回显，不保存）：')
    token=request('/api/auth/login','POST',{'username':username,'password':password})['access_token']
    password=''
    existing=set();page=1
    while True:
        data=request(f'/api/management/questions?status=all&page={page}&limit=100',token=token)
        for item in data['items']:existing.update(item.get('tags',[]))
        if page*100>=data['total']:break
        page+=1
    journal=ROOT/'work'/'import-journal.json'
    journal.parent.mkdir(exist_ok=True)
    log=[];created=0;skipped=0
    if journal.exists():log=json.loads(journal.read_text(encoding='utf-8'))
    for row in rows:
        qid=next(tag for tag in row['content']['tags'] if tag.startswith('C') and '-' in tag)
        if qid in existing:skipped+=1;continue
        result=request('/api/management/questions','POST',row,token)
        log.append({'source_id':qid,'app_question_id':result['id'],'status':'draft'})
        journal.write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
        existing.add(qid);created+=1
        print(f'{qid} 已建立草稿。')
    print(f'完成：新增草稿{created}道，按题号标签跳过已有题{skipped}道。未发布题目。')

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,urllib.error.URLError) as e:
        print(str(e),file=sys.stderr);sys.exit(1)
