import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import vm from "node:vm";

const appSource = readFileSync(
  new URL("../pharma_proto/static/app.js", import.meta.url),
  "utf8",
);

function fakeElement(initial = {}) {
  const listeners = new Map();
  return Object.assign({
    value: "",
    textContent: "",
    hidden: false,
    disabled: false,
    dataset: {},
    children: [],
    focused: false,
    addEventListener(type, listener) {
      listeners.set(type, listener);
    },
    async dispatch(type) {
      return listeners.get(type)?.();
    },
    append(child) {
      this.children.push(child);
      if (child.selected) this.value = child.value;
    },
    replaceChildren() {
      this.children = [];
      this.value = "";
    },
    focus() {
      this.focused = true;
    },
  }, initial);
}

function browserHarness({generatePayload} = {}) {
  const eventLog = [];
  const provider = fakeElement({value: "openai"});
  const tier = fakeElement({value: "normal"});
  const apiKey = fakeElement();
  const question = fakeElement({value: "배합 질문"});
  const results = fakeElement();
  const reviewNotice = fakeElement({hidden: true});
  const elements = {
    "#provider": provider,
    "#tier": tier,
    "#api-key": apiKey,
    "#question": question,
    "#message": fakeElement(),
    "#setup-message": fakeElement(),
    "#results": results,
    "#api-setup": fakeElement(),
    "#research-app": fakeElement({hidden: true}),
    "#review-notice": reviewNotice,
    "#selected-model": fakeElement(),
    "#model-catalog": fakeElement({
      textContent: JSON.stringify({
        openai: {
          cheap: "gpt-5.6-luna",
          normal: "gpt-5.6-terra",
          good: "gpt-5.6-sol",
        },
      }),
    }),
    "#health": fakeElement(),
    "#save-key": fakeElement(),
    "#change-key": fakeElement(),
    "#generate": fakeElement(),
  };

  Object.defineProperty(results, "innerHTML", {
    get() {
      return this._innerHTML || "";
    },
    set(value) {
      this._innerHTML = value;
      this.buttons = [...value.matchAll(/data-candidate-index="(\d+)"/g)].map(
        (match) => fakeElement({
          disabled: true,
          dataset: {candidateIndex: match[1]},
        }),
      );
      this.hasCard = value.includes('class="card"');
    },
  });
  results.replaceChildren = function replaceChildren() {
    this.innerHTML = "";
  };
  results.querySelectorAll = (selector) => (
    selector === ".download-xlsx" ? (results.buttons || []) : []
  );
  results.querySelector = (selector) => (
    selector === ".card" && results.hasCard ? {} : null
  );

  const body = {
    children: [],
    append(child) {
      child.isConnected = true;
      this.children.push(child);
      eventLog.push(["append", child.download]);
    },
  };

  const document = {
    body,
    querySelector(selector) {
      return elements[selector];
    },
    createElement(tag) {
      if (tag === "option") return fakeElement({selected: false});
      if (tag === "a") {
        const anchor = fakeElement({href: "", download: "", isConnected: false});
        anchor.click = () => eventLog.push([
          "click",
          anchor.download,
          anchor.isConnected,
        ]);
        anchor.remove = () => {
          anchor.isConnected = false;
          body.children = body.children.filter((item) => item !== anchor);
          eventLog.push(["remove", anchor.download]);
        };
        return anchor;
      }
      return fakeElement();
    },
  };

  const fetchCalls = [];
  async function fetch(url, options = {}) {
    fetchCalls.push([url, options]);
    const payload = url === "/health"
      ? {
          status: "ok",
          app_version: "0.1.0",
          snapshot_id: "test",
          schema_version: 1,
        }
      : url === "/api/generate"
        ? generatePayload
        : {provider: "openai", configured: true};
    return {ok: true, async json() { return payload; }};
  }

  let urlIndex = 0;
  const context = vm.createContext({
    document,
    fetch,
    console,
    Blob,
    Uint8Array,
    atob,
    URL: {
      createObjectURL() {
        const url = `blob:test-${++urlIndex}`;
        eventLog.push(["create", url]);
        return url;
      },
      revokeObjectURL(url) {
        eventLog.push(["revoke", url]);
      },
    },
    setTimeout(callback) {
      callback();
    },
  });
  vm.runInContext(appSource, context);

  return {elements, eventLog, fetchCalls, results};
}

test("API 확인 후 선택한 전체 모델명과 연구 화면을 표시한다", async () => {
  const harness = browserHarness();
  harness.elements["#api-key"].value = "test-key";

  await harness.elements["#save-key"].dispatch("click");

  assert.equal(harness.elements["#api-setup"].hidden, true);
  assert.equal(harness.elements["#research-app"].hidden, false);
  assert.equal(harness.elements["#selected-model"].textContent, "gpt-5.6-terra");
  assert.equal(harness.elements["#api-key"].value, "");
});

test("API 설정을 변경하면 이전 모델의 결과를 제거한다", async () => {
  const harness = browserHarness();
  harness.results.innerHTML = '<div class="card">이전 결과</div>';
  harness.elements["#review-notice"].hidden = false;

  await harness.elements["#change-key"].dispatch("click");

  assert.equal(harness.results.innerHTML, "");
  assert.equal(harness.elements["#review-notice"].hidden, true);
  assert.equal(harness.elements["#research-app"].hidden, true);
  assert.equal(harness.elements["#api-setup"].hidden, false);
});

test("생성된 후보 3개의 Excel 버튼을 각각 올바른 파일에 연결한다", async () => {
  const html = [1, 2, 3].map(
    (index) => `<div class="card"><button class="download-xlsx" data-candidate-index="${index}" disabled></button></div>`,
  ).join("");
  const downloads = [1, 2, 3].map((index) => ({
    candidate_idx: index,
    filename: `조성_후보_${index}.xlsx`,
    content_base64: "WA==",
  }));
  const harness = browserHarness({generatePayload: {html, downloads}});

  await harness.elements["#generate"].dispatch("click");

  assert.equal(harness.results.buttons.length, 3);
  assert.deepEqual(harness.results.buttons.map((button) => button.disabled), [false, false, false]);
  assert.equal(harness.elements["#review-notice"].hidden, false);

  for (const button of harness.results.buttons) await button.dispatch("click");
  const clicks = harness.eventLog.filter(([event]) => event === "click");
  assert.deepEqual(
    clicks,
    [1, 2, 3].map((index) => ["click", `조성_후보_${index}.xlsx`, true]),
  );
  assert.equal(harness.eventLog.filter(([event]) => event === "revoke").length, 3);
});
