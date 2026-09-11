import assert from "node:assert/strict";
import test from "node:test";

import {advanceComparison,changedInputKeys,compareDistance,createInputSnapshot} from "../../assets/js/dof/comparison-state.mjs";
import {formatDistanceDelta} from "../../assets/js/dof/formatters.mjs";

const snapshot=n=>createInputSnapshot({sensor:"ff_36x24",fNumber:String(n),focalLength:"50"});
const record=(n,farMm=3500)=>({inputSnapshot:snapshot(n),result:{farMm}});

test("first successful calculation has no previous result",()=>{
  assert.deepEqual(advanceComparison(null,record(1.2)).previous,null);
});

test("draft comparison detects value changes rather than input events",()=>{
  assert.deepEqual(changedInputKeys(snapshot(1.2),snapshot("1.20")),[]);
  assert.deepEqual(changedInputKeys(snapshot(1.2),snapshot(1.4)),["fNumber"]);
});

test("successful calculations advance only one step",()=>{
  let history=advanceComparison(null,record(1.2));
  history=advanceComparison(history,record(1.4));
  history=advanceComparison(history,record(2));
  assert.equal(history.previous.inputSnapshot.fNumber,1.4);
  assert.equal(history.current.inputSnapshot.fNumber,2);
});

test("arbitrary free-input f-numbers are normalized and compared",()=>{
  assert.deepEqual(changedInputKeys(snapshot(1.4),snapshot(3.5)),["fNumber"]);
});

test("focal length, focus, sensor, criterion, and custom values are compared",()=>{
  const before=createInputSnapshot({sensor:"ff_36x24",sensorWidth:"36",focalLength:"50",focusDistance:"3",criterion:"traditional_ff_0030",customCriterion:"30"});
  const after=createInputSnapshot({sensor:"custom",sensorWidth:"44",focalLength:"85",focusDistance:"2",criterion:"custom",customCriterion:"20"});
  assert.deepEqual(changedInputKeys(before,after),["sensor","sensorWidth","focalLength","focusDistance","criterion","customCriterion"]);
});

test("invalid attempts cannot mutate history unless explicitly advanced",()=>{
  const history=advanceComparison(advanceComparison(null,record(1.2)),record(1.4));
  const afterInvalid=history;
  assert.equal(afterInvalid.previous.inputSnapshot.fNumber,1.2);
  assert.equal(afterInvalid.current.inputSnapshot.fNumber,1.4);
});

test("finite to infinity is a state transition, not arithmetic",()=>{
  assert.deepEqual(compareDistance(10000,null),{kind:"transition",text:"有限 → ∞",label:"有限から無限へ変化"});
});

test("infinity to finite is a state transition, not arithmetic",()=>{
  assert.deepEqual(compareDistance(null,12400),{kind:"transition",text:"∞ → 有限",label:"無限から有限へ変化"});
});

test("unchanged values are suppressed",()=>{
  assert.deepEqual(compareDistance(1000,1000),{kind:"unchanged"});
  assert.deepEqual(compareDistance(null,null),{kind:"unchanged"});
});

test("distance deltas are rounded naturally and expose non-color semantics",()=>{
  assert.deepEqual(formatDistanceDelta(8.5000000001),{text:"↑ 8.5 mm",label:"増加 8.5 mm"});
  assert.deepEqual(formatDistanceDelta(-10),{text:"↓ 10.0 mm",label:"減少 10.0 mm"});
});
