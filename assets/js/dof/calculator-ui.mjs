import {calculateClassicDof,resolveCriterionPreset,resolveSensorPreset} from "./calculation-core.mjs";
import {renderBlurChart} from "./blur-chart.mjs";
import {advanceComparison,changedInputKeys,compareDistance,createInputSnapshot} from "./comparison-state.mjs";
import {formatCriterionMicrometers,formatDistance,formatDistanceDelta} from "./formatters.mjs";
import {parseRequiredNumber} from "./input-values.mjs";
import {DEFAULT_URL_STATE,parseUrlState} from "./url-state.mjs";

const $=id=>document.getElementById(id);const form=$("dof-form");let history=null;let draftChanged=false;let sensorExplainerShown=false;
const LANG=document.documentElement.lang==="en"?"en":"ja";
const UI_STRINGS={
  ja:{
    criterionCopy:{traditional_ff_0030:{description:"35mmフルサイズで伝統的に使われてきた代表的な30 µm固定の基準です。センサーサイズを変更しても30 µmのままです。",provenance:"Traditional 30 µm — REFERENCE"},format_diagonal_1500:{description:"センサーの対角線を1500で割った値を基準にします。35mmフルサイズでは約29 µmになり、APS-Cやマイクロフォーサーズではより小さな値になります。",provenance:"Sensor diagonal ÷ 1500 — REFERENCE"},custom:{description:"入力したセンサー面上の幾何学的ボケ径を、任意の許容基準として使用します。",provenance:"Custom geometric blur diameter — USER INPUT"}},
    sensorLabels:{ff_36x24:"35mmフルサイズ",apsc_canon_ref:"Canon APS-C",apsc_235x156_ref:"APS-C",mft_173x130:"マイクロフォーサーズ",custom:"カスタム"},
    criterionLabels:{traditional_ff_0030:"Traditional 30 µm",format_diagonal_1500:"センサー対角線 ÷ 1500",custom:"カスタム"},
    effectiveCriterionPrefix:"現在の許容錯乱円：",
    effectiveCriterionUnknown:"現在の許容錯乱円：—",
    previousPrefix:"前回",
    errors:{sensor:"0より大きい幅と高さを入力してください。",focus:"焦点距離より大きい、0より大きな値を入力してください。",focal:"0より大きい値を入力してください。",aperture:"0より大きい値を入力してください。",criterion:"0より大きい基準値を入力してください。",generic:"入力値を確認してください。"},
    chartSummary:(near,focusPos,far,criterion)=>`近点 ${near}、ピント位置 ${focusPos}、遠点 ${far}、許容するボケの基準 ${criterion}。その基準以下に収まる範囲が被写界深度です。`,
  },
  en:{
    criterionCopy:{traditional_ff_0030:{description:"A conventional fixed 30 µm criterion traditionally used for 35mm full-frame. It stays 30 µm even if you change the sensor format.",provenance:"Traditional 30 µm — REFERENCE"},format_diagonal_1500:{description:"Based on the sensor diagonal divided by 1500. About 29 µm for 35mm full-frame; smaller for APS-C or Micro Four Thirds.",provenance:"Sensor diagonal ÷ 1500 — REFERENCE"},custom:{description:"Uses the geometric blur diameter on the sensor plane that you enter as an arbitrary criterion.",provenance:"Custom geometric blur diameter — USER INPUT"}},
    sensorLabels:{ff_36x24:"Full Frame (35mm)",apsc_canon_ref:"Canon APS-C",apsc_235x156_ref:"APS-C",mft_173x130:"Micro Four Thirds",custom:"Custom"},
    criterionLabels:{traditional_ff_0030:"Traditional 30 µm",format_diagonal_1500:"Sensor diagonal ÷ 1500",custom:"Custom"},
    effectiveCriterionPrefix:"Current circle of confusion: ",
    effectiveCriterionUnknown:"Current circle of confusion: —",
    previousPrefix:"Previous",
    errors:{sensor:"Enter a width and height greater than 0.",focus:"Enter a focus distance greater than the focal length and greater than 0.",focal:"Enter a value greater than 0.",aperture:"Enter a value greater than 0.",criterion:"Enter a criterion value greater than 0.",generic:"Please check your input values."},
    chartSummary:(near,focusPos,far,criterion)=>`Near limit ${near}, focus position ${focusPos}, far limit ${far}, acceptable-blur criterion ${criterion}. The depth of field is the range within that criterion.`,
  },
};
const S=UI_STRINGS[LANG];
const resultFields={near:"nearMm","focus-result":"focusDistanceMm",far:"farMm",total:"totalDofMm",front:"frontDofMm",rear:"rearDofMm",hyperfocal:"hyperfocalMm"};

function applyState(s){$("dof-sensor").value=s.sensor;$("dof-focal").value=s.f;$("dof-aperture").value=s.n;$("dof-focus").value=s.s;$("dof-criterion").value=s.criterion;if(s.sw)$("dof-sensor-width").value=s.sw;if(s.sh)$("dof-sensor-height").value=s.sh;if(s.c)$("dof-criterion-value").value=s.c;toggleOptional();}
function number(id){return parseRequiredNumber($(id).value);}
function selectedCriterion(){const sensor=resolveSensorPreset($("dof-sensor").value,{widthMm:number("dof-sensor-width"),heightMm:number("dof-sensor-height")});return resolveCriterionPreset($("dof-criterion").value,{sensor,valueMm:number("dof-criterion-value")/1000});}
function updateCriterionUx(){const preset=$("dof-criterion").value;$("dof-criterion-explanation").textContent=S.criterionCopy[preset].description;$("dof-criterion-detail").textContent=S.criterionCopy[preset].provenance;try{$("dof-effective-criterion").textContent=`${S.effectiveCriterionPrefix}${formatCriterionMicrometers(selectedCriterion().valueMm)}`;}catch{$("dof-effective-criterion").textContent=S.effectiveCriterionUnknown;}}
function toggleOptional(){$("dof-custom-sensor").hidden=$("dof-sensor").value!=="custom";$("dof-custom-criterion").hidden=$("dof-criterion").value!=="custom";updateCriterionUx();}
function input(){const sensor=resolveSensorPreset($("dof-sensor").value,{widthMm:number("dof-sensor-width"),heightMm:number("dof-sensor-height")});const preset=$("dof-criterion").value;const criterion=resolveCriterionPreset(preset,{sensor,valueMm:number("dof-criterion-value")/1000});return {sensor,focalLengthMm:number("dof-focal"),fNumber:number("dof-aperture"),focusDistanceMm:number("dof-focus")*1000,criterion};}
function inputSnapshot(){return createInputSnapshot({sensor:$("dof-sensor").value,sensorWidth:$("dof-sensor-width").value,sensorHeight:$("dof-sensor-height").value,focalLength:$("dof-focal").value,fNumber:$("dof-aperture").value,focusDistance:$("dof-focus").value,criterion:$("dof-criterion").value,customCriterion:$("dof-criterion-value").value});}
function record(value,result){return {value,result,inputSnapshot:inputSnapshot(),display:{sensor:S.sensorLabels[$("dof-sensor").value],sensorWidth:$("dof-sensor-width").value,sensorHeight:$("dof-sensor-height").value,focalLength:$("dof-focal").value,fNumber:$("dof-aperture").value,focusDistance:$("dof-focus").value,criterion:S.criterionLabels[$("dof-criterion").value],effectiveCriterion:formatCriterionMicrometers(value.criterion.valueMm)}};}

function setPrevious(id,changed,text){const node=$(id);node.hidden=!changed;node.textContent=changed?`${S.previousPrefix} ${text}`:"";}
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
function showError(error){clearErrors();const codes=error.issues?.map(x=>x.code)||[];if(codes.some(x=>x.includes("SENSOR_WIDTH")||x.includes("SENSOR_HEIGHT")))$("dof-sensor-error").textContent=S.errors.sensor;else if(codes.some(x=>x.includes("FOCUS_DISTANCE")))$("dof-focus-error").textContent=S.errors.focus;else if(codes.some(x=>x.includes("FOCAL")))$("dof-focal-error").textContent=S.errors.focal;else if(codes.some(x=>x.includes("F_NUMBER")))$("dof-aperture-error").textContent=S.errors.aperture;else if(codes.some(x=>x.includes("CRITERION")))$("dof-criterion-error").textContent=S.errors.criterion;else{$("dof-form-error").hidden=false;$("dof-form-error").textContent=S.errors.generic;}}
function renderDeltas(){for(const [id,key] of Object.entries(resultFields)){const node=$(`dof-${id}-delta`);node.hidden=true;node.textContent="";node.removeAttribute("aria-label");if(!history.previous)continue;const comparison=compareDistance(history.previous.result[key],history.current.result[key],LANG);if(comparison.kind==="unchanged")continue;if(comparison.kind==="transition"){node.textContent=comparison.text;node.setAttribute("aria-label",comparison.label);}else{const formatted=formatDistanceDelta(comparison.deltaMm,LANG);node.textContent=formatted.text;node.setAttribute("aria-label",formatted.label);}node.hidden=false;}}
function renderCurrent(){const result=history.current.result;for(const [id,key] of Object.entries(resultFields))$(`dof-${id}`).textContent=formatDistance(result[key]);const warning=result.warnings.some(x=>x.code==="CLOSE_FOCUS_MODEL_LIMIT");$("dof-warning").hidden=!warning;$("dof-warning-detail").hidden=!warning;renderDeltas();}
function calculate(){try{clearErrors();const value=input(),result=calculateClassicDof(value);if(history?.current&&changedInputKeys(history.current.inputSnapshot,inputSnapshot()).length===0){draftChanged=false;updateInputComparison();return true;}history=advanceComparison(history,record(value,result));draftChanged=false;renderCurrent();updateCriterionUx();updateInputComparison();if($("dof-curve-disclosure").open)draw();return true;}catch(error){showError(error);updateInputComparison();return false;}}
function maybeShowSensorExplainer(){if(sensorExplainerShown||$("dof-criterion").value!=="traditional_ff_0030")return;sensorExplainerShown=true;$("dof-sensor-explainer").showModal();}
function draw(){if(!history?.current)return;const {value,result}=history.current;renderBlurChart($("dof-chart"),value,result,LANG);$("dof-chart-summary").textContent=S.chartSummary(formatDistance(result.nearMm),formatDistance(result.focusDistanceMm),formatDistance(result.farMm),formatCriterionMicrometers(value.criterion.valueMm));}
function noteDraftChange(){draftChanged=true;updateInputComparison();}

form.addEventListener("submit",e=>{e.preventDefault();});form.addEventListener("input",noteDraftChange);form.addEventListener("change",e=>{const sensorChanged=e.target===$("dof-sensor");if(sensorChanged||e.target===$("dof-criterion"))toggleOptional();noteDraftChange();const ok=calculate();if(sensorChanged&&ok)maybeShowSensorExplainer();});
form.addEventListener("keydown",e=>{if(e.key==="Enter"&&e.target.tagName==="INPUT"&&e.target.type==="number"){e.preventDefault();calculate();}});
for(const id of ["dof-sensor-width","dof-sensor-height","dof-criterion-value"])$(id).addEventListener("input",updateCriterionUx);
for(const button of document.querySelectorAll("[data-fnumber]"))button.addEventListener("click",()=>{$("dof-aperture").value=button.dataset.fnumber;noteDraftChange();calculate();$("dof-aperture").focus();});
$("dof-curve-disclosure").addEventListener("toggle",()=>{if($("dof-curve-disclosure").open)draw();});
$("dof-sensor-explainer").addEventListener("close",()=>{$("dof-sensor").focus();});
const parsed=parseUrlState(location.search);applyState(parsed.ok?parsed.state:DEFAULT_URL_STATE);calculate();$("dof-url-warning").hidden=parsed.ok;
