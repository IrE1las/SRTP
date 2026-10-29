"""Create a NEW isolated acceptance DB under .runtime, never overwrite any DB."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    path = Path(args.database).resolve()
    if not path.is_relative_to((ROOT / '.runtime').resolve()) or path.exists():
        raise SystemExit('仅允许项目.runtime内不存在的新文件；不会覆盖现有数据库。')
    path.parent.mkdir(parents=True, exist_ok=True)
    # Set before importing configuration or database bindings.
    os.environ['DATABASE_URL'] = 'sqlite:///' + path.as_posix()
    os.environ['SECRET_KEY'] = 's3-isolated-acceptance-development-only'
    os.environ['DEEPSEEK_API_KEY'] = ''
    sys.path.insert(0, str(ROOT / 'framework/backend'))
    from main import on_startup
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models import User
    on_startup()
    with SessionLocal() as db:
        for name, role, number, cls in [
            ('s3_teacher_a','teacher',None,None), ('s3_teacher_b','teacher',None,None),
            ('s3_student_a','student','S3-QA-01','S3验收一班'),
            ('s3_student_b','student','S3-QA-02','S3验收二班'),
        ]:
            db.add(User(username=name, role=role, real_name='S3验收账号', student_id=number,
                        class_name=cls, password_hash=get_password_hash('S3test123')))
        db.commit()
    print(f'Created isolated acceptance database: {path}')
    print('Four s3_* synthetic accounts only; password S3test123. Isolated admin: admin / 00000000.')


if __name__ == '__main__':
    main()
