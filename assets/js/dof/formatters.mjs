export function formatDistance(mm){
  if(mm===null)return "∞";
  if(mm>=10000)return `${(mm/1000).toFixed(1)} m`;
  if(mm>=100)return `${(mm/1000).toFixed(2)} m`;
  return `${mm.toFixed(1)} mm`;
}

export function formatCriterionMicrometers(valueMm){
  return `${(valueMm*1000).toFixed(1)} µm`;
}
