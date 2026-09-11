export function formatDistance(mm){
  if(mm===null)return "∞";
  if(mm>=10000)return `${(mm/1000).toFixed(1)} m`;
  if(mm>=100)return `${(mm/1000).toFixed(2)} m`;
  return `${mm.toFixed(1)} mm`;
}

export function formatCriterionMicrometers(valueMm){
  return `${(valueMm*1000).toFixed(1)} µm`;
}

const DELTA_WORDS={ja:{increase:"増加",decrease:"減少"},en:{increase:"increase",decrease:"decrease"}};

export function formatDistanceDelta(deltaMm,lang="ja"){
  const words=DELTA_WORDS[lang]||DELTA_WORDS.ja;
  const direction=deltaMm>0?words.increase:words.decrease;
  const arrow=deltaMm>0?"↑":"↓";
  const value=formatDistance(Math.abs(deltaMm));
  return {text:`${arrow} ${value}`,label:`${direction} ${value}`};
}
