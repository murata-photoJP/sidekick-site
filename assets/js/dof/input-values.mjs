export function parseRequiredNumber(value){
  if(typeof value!=="string"||value.trim()==="")return Number.NaN;
  const parsed=Number(value);
  return Number.isFinite(parsed)?parsed:Number.NaN;
}
