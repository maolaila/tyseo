(() => {
  const result={supported:false,value:0,entries:0,startedAt:performance.now(),scope:'bounded lab observation; not field p75'};
  window.__layoutShiftAudit=result;
  if(!window.PerformanceObserver || !PerformanceObserver.supportedEntryTypes.includes('layout-shift'))return;
  result.supported=true;
  let start=0,last=0,total=0;
  new PerformanceObserver(list=>{
    for(const entry of list.getEntries()){
      if(entry.hadRecentInput)continue;
      if(entry.startTime-last<1000 && entry.startTime-start<5000)total+=entry.value;
      else {start=entry.startTime;total=entry.value;}
      last=entry.startTime;result.entries++;result.value=Math.max(result.value,total);
    }
  }).observe({type:'layout-shift',buffered:true});
})();
