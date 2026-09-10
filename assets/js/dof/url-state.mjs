export const URL_STATE_VERSION = "1";
export const DEFAULT_URL_STATE = Object.freeze({sensor:"ff_36x24",f:50,n:4,s:3,criterion:"traditional_ff_0030"});
const SENSORS=new Set(["ff_36x24","apsc_canon_ref","apsc_235x156_ref","mft_173x130","custom"]);
const CRITERIA=new Set(["traditional_ff_0030","format_diagonal_1500","custom"]);
const positive=value=>Number.isFinite(Number(value))&&Number(value)>0;
export function parseUrlState(search){
  const p=new URLSearchParams(search); if(!p.size)return {ok:true,state:{...DEFAULT_URL_STATE},issues:[]};
  const issues=[]; const state={v:p.get("v"),sensor:p.get("sensor"),f:Number(p.get("f")),n:Number(p.get("n")),s:Number(p.get("s")),criterion:p.get("criterion")};
  if(state.v!==URL_STATE_VERSION)issues.push("INVALID_VERSION"); if(!SENSORS.has(state.sensor))issues.push("UNKNOWN_SENSOR");
  for(const key of ["f","n","s"])if(!positive(state[key]))issues.push(`INVALID_${key.toUpperCase()}`);
  if(!CRITERIA.has(state.criterion))issues.push("UNKNOWN_CRITERION");
  if(state.sensor==="custom"){state.sw=Number(p.get("sw"));state.sh=Number(p.get("sh"));if(!positive(state.sw)||!positive(state.sh))issues.push("CUSTOM_SENSOR_REQUIRED");}
  if(state.criterion==="custom"){state.c=Number(p.get("c"));if(!positive(state.c))issues.push("CUSTOM_CRITERION_REQUIRED");}
  return {ok:issues.length===0,state:issues.length?null:state,issues};
}
export function serializeUrlState(state){
  const p=new URLSearchParams({v:URL_STATE_VERSION,sensor:state.sensor,f:String(state.f),n:String(state.n),s:String(state.s),criterion:state.criterion});
  if(state.sensor==="custom"){p.set("sw",String(state.sw));p.set("sh",String(state.sh));} if(state.criterion==="custom")p.set("c",String(state.c)); return `?${p}`;
}
