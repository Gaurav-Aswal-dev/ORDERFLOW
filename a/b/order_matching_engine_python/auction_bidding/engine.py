from datetime import datetime,timezone,timedelta
from .storage import connect,init
init()
def dt():return datetime.now(timezone.utc)
def iso(x):return x.isoformat()
def _close_expired(db,aid=None):
 now=iso(dt()); where=' AND auction_id=?' if aid else ''; args=[now]+([aid] if aid else [])
 rows=db.execute("SELECT auction_id FROM auctions WHERE status='OPEN' AND ends_at<=?"+where,args).fetchall()
 for row in rows:
  top=db.execute('SELECT bidder,amount FROM bids WHERE auction_id=? ORDER BY amount DESC,placed_at ASC,bid_id ASC LIMIT 1',(row['auction_id'],)).fetchone()
  db.execute("UPDATE auctions SET status='CLOSED',closed_at=?,winner=?,winning_bid=? WHERE auction_id=?",(now,top['bidder'] if top else None,top['amount'] if top else None,row['auction_id']))
def create(symbol,title,start,duration):
 now=dt(); end=now+timedelta(minutes=duration)
 with connect() as db:
  cur=db.execute("INSERT INTO auctions(symbol,title,starting_price,status,created_at,ends_at) VALUES(?,?,?,'OPEN',?,?)",(symbol.upper(),title,start,iso(now),iso(end)))
 return get(cur.lastrowid)
def bid(aid,bidder,amount):
 with connect() as db:
  _close_expired(db,aid); a=db.execute('SELECT * FROM auctions WHERE auction_id=?',(aid,)).fetchone()
  if not a:raise ValueError('Auction not found')
  if a['status']!='OPEN':raise ValueError('Auction is closed')
  top=db.execute('SELECT MAX(amount) m FROM bids WHERE auction_id=?',(aid,)).fetchone()['m']; minimum=max(float(a['starting_price']),float(top or 0))
  if amount<=minimum:raise ValueError(f'Bid must exceed current high bid/starting price ({minimum})')
  db.execute('INSERT INTO bids(auction_id,bidder,amount,placed_at) VALUES(?,?,?,?)',(aid,bidder.strip(),amount,iso(dt())))
 return get(aid)
def close(aid):
 with connect() as db:
  a=db.execute('SELECT * FROM auctions WHERE auction_id=?',(aid,)).fetchone()
  if not a:raise ValueError('Auction not found')
  if a['status']=='OPEN':
   top=db.execute('SELECT bidder,amount FROM bids WHERE auction_id=? ORDER BY amount DESC,placed_at ASC,bid_id ASC LIMIT 1',(aid,)).fetchone()
   db.execute("UPDATE auctions SET status='CLOSED',closed_at=?,winner=?,winning_bid=? WHERE auction_id=?",(iso(dt()),top['bidder'] if top else None,top['amount'] if top else None,aid))
 return get(aid)
def get(aid):
 with connect() as db:
  _close_expired(db,aid); row=db.execute('SELECT * FROM auctions WHERE auction_id=?',(aid,)).fetchone()
  if not row:return None
  out=dict(row);out['bids']=[dict(x) for x in db.execute('SELECT * FROM bids WHERE auction_id=? ORDER BY amount DESC,placed_at',(aid,))];return out
def list_all():
 with connect() as db:
  _close_expired(db);return [dict(x) for x in db.execute('SELECT * FROM auctions ORDER BY auction_id DESC LIMIT 200')]
