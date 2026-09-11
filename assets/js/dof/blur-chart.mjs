import {sampleContinuousCurve} from "./calculation-core.mjs";
import {formatCriterionMicrometers,formatDistance} from "./formatters.mjs";

const esc=value=>String(value).replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));

const CHART_STRINGS={
  ja:{near:"近点",focus:"ピント",far:"遠点",withinRange:"この先も許容範囲 →",dofLabel:"被写界深度",title:"被写体距離と計算上のボケ径",criterionPrefix:"許容するボケの基準：",curveLabel:"計算上のボケ径",xAxis:"被写体距離 (m)",yAxis:"センサー面上のボケ径 (µm)",description:(criterionLabel,near,far)=>`計算上のボケ径はピント位置で最小です。許容するボケの基準は${criterionLabel}。近点 ${near}から遠点 ${far}までが許容範囲です。`},
  en:{near:"Near",focus:"Focus",far:"Far",withinRange:"Within criterion beyond this point →",dofLabel:"Depth of field",title:"Object distance vs. calculated blur diameter",criterionPrefix:"Criterion (max acceptable blur): ",curveLabel:"Calculated blur diameter",xAxis:"Object distance (m)",yAxis:"Blur diameter at sensor (µm)",description:(criterionLabel,near,far)=>`Calculated blur is smallest at the focus position. The acceptable-blur criterion is ${criterionLabel}. The range from ${near} to ${far} stays within that criterion.`},
};

export function curveWindow(result){
  const focus=result.focusDistanceMm,near=result.nearMm;
  return {startObjectDistanceMm:Math.max(focus*.15,near-(focus-near)*1.25),endObjectDistanceMm:result.farIsInfinite?Math.max(focus*3,result.hyperfocalMm*1.35):result.farMm+(result.farMm-focus)*1.25};
}

export function renderBlurChart(container,input,result,lang="ja"){
  const S=CHART_STRINGS[lang]||CHART_STRINGS.ja;
  const range=curveWindow(result),curve=sampleContinuousCurve(input,{...range,sampleCount:161});
  const W=800,H=360,left=58,right=48,top=62,bottom=56;
  const criterionLabel=formatCriterionMicrometers(input.criterion.valueMm);
  const maxBlur=Math.max(input.criterion.valueMm*1.8,...curve.samples.map(point=>point.blurMm));
  const x=value=>left+(value-range.startObjectDistanceMm)/(range.endObjectDistanceMm-range.startObjectDistanceMm)*(W-left-right);
  const y=value=>H-bottom-value/maxBlur*(H-top-bottom);
  const path=curve.samples.map((point,index)=>`${index?"L":"M"}${x(point.objectDistanceMm).toFixed(2)},${y(point.blurMm).toFixed(2)}`).join(" ");
  const markers=[{value:result.nearMm,label:S.near},{value:result.focusDistanceMm,label:S.focus}];if(!result.farIsInfinite)markers.push({value:result.farMm,label:S.far});
  const bandStart=x(result.nearMm),bandEnd=result.farIsInfinite?W-right:x(result.farMm);
  const infinityNote=result.farIsInfinite?`<text class="range-label" text-anchor="end" x="${W-right}" y="${H-bottom-8}">${S.withinRange}</text>`:`<text class="range-label" text-anchor="middle" x="${(bandStart+bandEnd)/2}" y="${H-bottom-8}">${S.dofLabel}</text>`;
  const description=S.description(criterionLabel,formatDistance(result.nearMm),formatDistance(result.farMm));
  container.innerHTML=`<svg class="dof-chart" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="dof-chart-title dof-chart-desc"><title id="dof-chart-title">${S.title}</title><desc id="dof-chart-desc">${esc(description)}</desc><line class="axis" x1="${left}" y1="${H-bottom}" x2="${W-right}" y2="${H-bottom}"/><line class="axis" x1="${left}" y1="${top}" x2="${left}" y2="${H-bottom}"/><rect class="dof-range" x="${bandStart}" y="${y(input.criterion.valueMm)}" width="${Math.max(0,bandEnd-bandStart)}" height="${H-bottom-y(input.criterion.valueMm)}"/><line class="criterion" x1="${left}" y1="${y(input.criterion.valueMm)}" x2="${W-right}" y2="${y(input.criterion.valueMm)}"/><text class="criterion-label" x="${left+4}" y="${y(input.criterion.valueMm)-8}">${S.criterionPrefix}${criterionLabel}</text><path class="curve" d="${path}"/><text class="curve-label" x="${left+8}" y="${top+16}">${S.curveLabel}</text>${markers.map(marker=>`<line class="marker" x1="${x(marker.value)}" y1="${top}" x2="${x(marker.value)}" y2="${H-bottom}"/><text x="${x(marker.value)+4}" y="${H-bottom+18}">${marker.label}</text>`).join("")}${infinityNote}<text x="${W/2-55}" y="${H-10}">${S.xAxis}</text><text x="6" y="20">${S.yAxis}</text></svg>`;
  return curve;
}
