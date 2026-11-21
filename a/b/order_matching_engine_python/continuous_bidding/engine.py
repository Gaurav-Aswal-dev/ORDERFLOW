from .storage import connect,init,now
init()
def submit(symbol,side,price,qty):
 symbol=symbol.strip().upper(); fills=[]; remaining=qty
 with connect() as db:
  oid=db.execute('INSERT INTO orders(symbol,side,price,quantity,remaining,status,created_at) VALUES(?,?,?,?,?,?,?)',(symbol,side,price,qty,qty,'OPEN',now())).lastrowid
  opposite='SELL' if side=='BUY' else 'BUY'; comparator='<=?' if side=='BUY' else '>=?'; sort='price ASC,created_at ASC,order_id ASC' if side=='BUY' else 'price DESC,created_at ASC,order_id ASC'
  rows=db.execute(f"SELECT * FROM orders WHERE symbol=? AND side=? AND status IN ('OPEN','PARTIAL') AND remaining>0 AND price {comparator} ORDER BY {sort}",(symbol,opposite,price)).fetchall()
  for resting in rows:
   if remaining<=0: break
   q=min(remaining,resting['remaining']); trade_price=float(resting['price']); buy_id=oid if side=='BUY' else resting['order_id']; sell_id=resting['order_id'] if side=='BUY' else oid
   db.execute('INSERT INTO trades(symbol,buy_order_id,sell_order_id,price,quantity,executed_at) VALUES(?,?,?,?,?,?)',(symbol,buy_id,sell_id,trade_price,q,now()))
   nr=resting['remaining']-q; db.execute('UPDATE orders SET remaining=?,status=? WHERE order_id=?',(nr,'FILLED' if nr==0 else 'PARTIAL',resting['order_id']))
   remaining-=q; fills.append({'price':trade_price,'quantity':q,'against_order':resting['order_id']})
  db.execute('UPDATE orders SET remaining=?,status=? WHERE order_id=?',(remaining,'FILLED' if remaining==0 else ('PARTIAL' if fills else 'OPEN'),oid))
 return {'order_id':oid,'symbol':symbol,'side':side,'price':price,'quantity':qty,'remaining':remaining,'status':'FILLED' if remaining==0 else ('PARTIAL' if fills else 'OPEN'),'fills':fills}
def book(symbol):
 with connect() as db:
  buys=[dict(x) for x in db.execute("SELECT order_id,price,remaining quantity,created_at FROM orders WHERE symbol=? AND side='BUY' AND remaining>0 AND status IN ('OPEN','PARTIAL') ORDER BY price DESC,created_at LIMIT 100",(symbol.upper(),))]
  sells=[dict(x) for x in db.execute("SELECT order_id,price,remaining quantity,created_at FROM orders WHERE symbol=? AND side='SELL' AND remaining>0 AND status IN ('OPEN','PARTIAL') ORDER BY price ASC,created_at LIMIT 100",(symbol.upper(),))]
 return {'symbol':symbol.upper(),'buys':buys,'sells':sells}
def cancel(order_id):
 with connect() as db: return db.execute("UPDATE orders SET status='CANCELLED' WHERE order_id=? AND remaining>0 AND status IN ('OPEN','PARTIAL')",(order_id,)).rowcount>0
def history(symbol=None,limit=100):
 with connect() as db:
  q='SELECT * FROM trades'; args=[]
  if symbol:q+=' WHERE symbol=?';args.append(symbol.upper())
  q+=' ORDER BY trade_id DESC LIMIT ?';args.append(limit)
  return [dict(x) for x in db.execute(q,args)]
