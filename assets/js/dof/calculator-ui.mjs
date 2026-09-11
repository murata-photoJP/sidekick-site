import {calculateClassicDof,resolveCriterionPreset,resolveSensorPreset} from "./calculation-core.mjs";
import {renderBlurChart} from "./blur-chart.mjs";
import {advanceComparison,changedInputKeys,compareDistance,createInputSnapshot} from "./comparison-state.mjs";
import {formatCriterionMicrometers,formatDistance,formatDistanceDelta} from "./formatters.mjs";
import {parseRequiredNumber} from "./input-values.mjs";
import {DEFAULT_URL_STATE,parseUrlState} from "./url-state.mjs";

const $=id=>document.getElementById(id);const form=$("dof-form");let history=null;let draftChanged=false;let sensorExplainerShown=false;
const criterionCopy={traditional_ff_0030:{description:"35mmフルサイズで伝統的に使われてきた代表的な30 µm固定の基準です。センサーサイズを変更しても30 µmのままです。",provenance:"Traditional 30 µm — REFERENCE"},format_diagonal_1500:{description:"センサーの対角線を1500で割った値を基準にします。35mmフルサイズでは約29 µmになり、APS-Cやマイクロフォーサーズではより小さな値になります。",provenance:"Sensor diagonal ÷ 1500 — REFERENCE"},custom:{description:"入力したセンサー面上の幾何学的ボケ径を、任意の許容基準として使用します。",provenance:"Custom geometric blur diameter — USER INPUT"}};
const sensorLabels={ff_36x24:"35mmフルサイズ",apsc_canon_ref:"Canon APS-C",apsc_235x156_ref:"APS-C",mft_173x130:"マイクロフォーサーズ",custom:"カスタム"};
const criterionLabels={traditional_ff_0030:"Traditional 30 µm",format_diagonal_1500:"センサー対角線 ÷ 1500",custom:"カスタム"};
const resultFields={near:"nearMm","focus-result":"focusDistanceMm",far:"farMm",total:"totalDofMm",front:"frontDofMm",rear:"rearDofMm",hyperfocal:"hyperfocalMm"};

function applyState(s){$("dof-sensor").value=s.sensor;$("dof-focal").value=s.f;$("dof-aperture").value=s.n;$("dof-focus").value=s.s;$("dof-criterion").value=s.criterion;if(s.sw)$("dof-sensor-width").value=s.sw;if(s.sh)$("dof-sensor-height").value=s.sh;if(s.c)$("dof-criterion-value").value=s.c;toggleOptional();}
function number(id){return parseRequiredNumber($(id).value);}
function selectedCriterion(){const sensor=resolveSensorPreset($("dof-sensor").value,{widthMm:number("dof-sensor-width"),heightMm:number("dof-sensor-height")});return resolveCriterionPreset($("dof-criterion").value,{sensor,valueMm:number("dof-criterion-value")/1000});}
function updateCriterionUx(){const preset=$("dof-criterion").value;$("dof-criterion-explanation").textContent=criterionCopy[preset].description;$("dof-criterion-detail").textContent=criterionCopy[preset].provenance;try{$("dof-effective-criterion").textContent=`現在の許容錯乱円：${formatCriterionMicrometers(selectedCriterion().valueMm)}`;}catch{$("dof-effective-criterion").textContent="現在の許容錯乱円：—";}}
function toggleOptional(){$("dof-custom-sensor").hidden=$("dof-sensor").value!=="custom";$("dof-custom-criterion").hidden=$("dof-criterion").value!=="custom";updateCriterionUx();}
function input(){const sensor=resolveSensorPreset($("dof-sensor").value,{widthMm:number("dof-sensor-width"),heightMm:number("dof-sensor-height")});const preset=$("dof-criterion").value;const criterion=resolveCriterionPreset(preset,{sensor,valueMm:number("dof-criterion-value")/1000});return {sensor,focalLengthMm:number("dof-focal"),fNumber:number("dof-aperture"),focusDistanceMm:number("dof-focus")*1000,criterion};}
function inputSnapshot(){return createInputSnapshot({sensor:$("dof-sensor").value,sensorWidth:$("dof-sensor-width").value,sensorHeight:$("dof-sensor-height").value,focalLength:$("dof-focal").value,fNumber:$("dof-aperture").value,focusDistance:$("dof-focus").value,criterion:$("dof-criterion").value,customCriterion:$("dof-criterion-value").value});}
function record(value,result){return {value,result,inputSnapshot:inputSnapshot(),display:{sensor:sensorLabels[$("dof-sensor").value],sensorWidth:$("dof-sensor-width").value,sensorHeight:$("dof-sensor-height").value,focalLength:$("dof-focal").value,fNumber:$("dof-aperture").value,focusDistance:$("dof-focus").value,criterion:criterionLabels[$("dof-criterion").value],effectiveCriterion:formatCriterionMicrometers(value.criterion.valueMm)}};}

function setPrevious(id,changed,text){const node=$(id);node.hidden=!changed;node.textContent=changed?`前回 ${text}`:"";}
function markField(name,changed){const node=form.querySelector(`[data-comparison-field="${name}"]`);if(node)node.dataset.changed=String(changed);}
function updateInputComparison(){
  const baseline=draftChanged?history?.current:history?.previous;
  if(!baseline){for(const node of form.querySelectorAll("[data-comparison-field]"))delete node.dataset.changed;for(const node of form.querySelectorAll(".dof-previous-input"))node.hidden=true;return;}
  const current=inputSnapshot();const changed=new Set(changedInputKeys(baseline.inputSnapshot,current));let effectiveCriterionChanged=false;
  try{effectiveCriterionChanged=Math.abs(selectedCriterion().valueMm-baseline.value.criterion.valueMm)>1e-12;}catch{}
  const groups={sensor:changed.has("sensor"),customSensor:changed.has("sensorWidth")||changed.has("sensorHeight"),focalLength:changed.has("focalLength"),fNumber:changed.has("fNumber"),focusDistance:changed.has("focusDistance"),criterion:changed.has("criterion")||changed.has("customCriterion")||effectiveCriterionChanged};
  for(const [name,value] of Object.entries(groups))markField(name,value);
  setPrevious("dof-previous-sensor",groups.sensor,baseline.display.sensor);setPrevious("dof-previous-custom-sensor",groups.customSensor&&baseline.inputSnapshot.sensor==="custom",`${baseline.display.sensorWidth} × ${baseline.display.sensorHeight} mm`);setPrevious("dof-previous-focal",groups.focalLength,`${baseline.display.focalLength} mm`);setPrevious("dof-previous-aperture",groups.fNumber,`F${baseline.display.fNumber}`);setPrevious("dof-previous-focus",groups.focusDistance,`${baseline.display.focusDistance} m`);setPrevious("dof-previous-criterion",groups.criterion,`${baseline.display.criterion}（${baseline.display.effectiveCriterion}）`);
}

function clearErrors(){for(const id of ["sensor","focal","aperture","focus","criterion"])$(`dof-${id}-error`).textContent="";$("dof-form-error").hidden=true;}
function showError(error){clearErrors();const codes=error.issues?.map(x=>x.code)||[];if(codes.some(x=>x.includes("SENSOR_WIDTH")||x.includes("SENSOR_HEIGHT")))$("dof-sensor-error").textContent="0より大きい幅と高さを入力してください。";else if(codes.some(x=>x.includes("FOCUS_DISTANCE")))$("dof-focus-error").textContent="焦点距離より大きい、0より大きな値を入力してください。";else if(codes.some(x=>x.includes("FOCAL")))$("dof-focal-error").textContent="0より大きい値を入力してください。";else if(codes.some(x=>x.includes("F_NUMBER")))$("dof-aperture-error").textContent="0より大きい値を入力してください。";else if(codes.some(x=>x.includes("CRITERION")))$("dof-criterion-error").textContent="0より大きい基準値を入力してください。";else{$("dof-form-error").hidden=false;$("dof-form-error").textContent="入力値を確認してください。";}}
function renderDeltas(){for(const [id,key] of Object.entries(resultFields)){const node=$(`dof-${id}-delta`);node.hidden=true;node.textContent="";node.removeAttribute("aria-label");if(!history.previous)continue;const comparison=compareDistance(history.previous.result[key],history.current.result[key]);if(comparison.kind==="unchanged")continue;if(comparison.kind==="transition"){node.textContent=comparison.text;node.setAttribute("aria-label",comparison.label);}else{const formatted=formatDistanceDelta(comparison.deltaMm);node.textContent=formatted.text;node.setAttribute("aria-label",formatted.label);}node.hidden=false;}}
function renderCurrent(){const result=history.current.result;for(const [id,key] of Object.entries(resultFields))$(`dof-${id}`).textContent=formatDistance(result[key]);const warning=result.warnings.some(x=>x.code==="CLOSE_FOCUS_MODEL_LIMIT");$("dof-warning").hidden=!warning;$("dof-warning-detail").hidden=!warning;renderDeltas();}
function calculate(){try{clearErrors();const value=input(),result=calculateClassicDof(value);if(history?.current&&changedInputKeys(history.current.inputSnapshot,inputSnapshot()).length===0){draftChanged=false;updateInputComparison();return true;}history=advanceComparison(history,record(value,result));draftChanged=false;renderCurrent();updateCriterionUx();updateInputComparison();if($("dof-curve-disclosure").open)draw();return true;}catch(error){showError(error);updateInputComparison();return false;}}
function maybeShowSensorExplainer(){if(sensorExplainerShown||$("dof-criterion").value!=="traditional_ff_0030")return;sensorExplainerShown=true;$("dof-sensor-explainer").showModal();}
function draw(){if(!history?.current)return;const {value,result}=history.current;renderBlurChart($("dof-chart"),value,result);$("dof-chart-summary").textContent=`近点 ${formatDistance(result.nearMm)}、ピント位置 ${formatDistance(result.focusDistanceMm)}、遠点 ${formatDistance(result.farMm)}、許容するボケの基準 ${formatCriterionMicrometers(value.criterion.valueMm)}。その基準以下に収まる範囲が被写界深度です。`;}
function noteDraftChange(){draftChanged=true;updateInputComparison();}

form.addEventListener("submit",e=>{e.preventDefault();});form.addEventListener("input",noteDraftChange);form.addEventListener("change",e=>{const sensorChanged=e.target===$("dof-sensor");if(sensorChanged||e.target===$("dof-criterion"))toggleOptional();noteDraftChange();const ok=calculate();if(sensorChanged&&ok)maybeShowSensorExplainer();});
form.addEventListener("keydown",e=>{if(e.key==="Enter"&&e.target.tagName==="INPUT"&&e.target.type==="number"){e.preventDefault();calculate();}});
for(const id of ["dof-sensor-width","dof-sensor-height","dof-criterion-value"])$(id).addEventListener("input",updateCriterionUx);
for(const button of document.querySelectorAll("[data-fnumber]"))button.addEventListener("click",()=>{$("dof-aperture").value=button.dataset.fnumber;noteDraftChange();calculate();$("dof-aperture").focus();});
$("dof-curve-disclosure").addEventListener("toggle",()=>{if($("dof-curve-disclosure").open)draw();});
$("dof-sensor-explainer").addEventListener("close",()=>{$("dof-sensor").focus();});
const parsed=parseUrlState(location.search);applyState(parsed.ok?parsed.state:DEFAULT_URL_STATE);calculate();$("dof-url-warning").hidden=parsed.ok;
