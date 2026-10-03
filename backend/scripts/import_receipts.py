"""Explicit offline migration utility; defaults to validation only."""
import argparse,json
from app.db import Session
from app.services.receipt_import import import_receipts

def main():
    p=argparse.ArgumentParser()
    p.add_argument('file');p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    with Session() as db:print(json.dumps(import_receipts(db,args.file,apply=args.apply)))

if __name__=='__main__':main()
