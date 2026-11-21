# Auction Bidding
Independent stock auction workflow: create timed auctions, accept bids strictly above starting/current high bid, close manually or automatically on expiry, and record highest bidder and winning amount. API is mounted by `dashboard.app` under `/api/auctions`; SQLite is `database/auction_bidding.db`.
