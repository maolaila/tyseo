"""Batch completion gate only. UI observations, not this helper, establish purchase/deployment."""
def completion(state):
    domains=state.get('domains',[])
    expected=state.get('expected_count')
    names=[x.get('domain') for x in domains]
    if not expected or len(domains)!=expected or len(set(names))!=expected or any(not x for x in names):
        return {'completed':False,'reason':'batch inventory mismatch'}
    verified=[];pending=[]
    for item in domains:
        receipt=item.get('submission') or {};site=item.get('verification') or {}
        good=(item.get('status')=='verified' and bool(item.get('purchase_evidence'))
              and receipt.get('status')=='confirmed' and bool(receipt.get('evidence'))
              and site.get('status')=='passed' and bool(site.get('evidence')))
        (verified if good else pending).append(item['domain'])
    return {'completed':not pending,'verified_count':len(verified),'pending_count':len(pending),'pending_domains':pending}
