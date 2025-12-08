import{r as a,W as x,j as Z,c as Le}from"./index-DMoMzkg2.js";function se(e,t){(t==null||t>e.length)&&(t=e.length);for(var r=0,n=Array(t);r<t;r++)n[r]=e[r];return n}function Ae(e){if(Array.isArray(e))return e}function Te(e,t,r){return(t=We(t))in e?Object.defineProperty(e,t,{value:r,enumerable:!0,configurable:!0,writable:!0}):e[t]=r,e}function Ie(e,t){var r=e==null?null:typeof Symbol<"u"&&e[Symbol.iterator]||e["@@iterator"];if(r!=null){var n,o,i,u,c=[],s=!0,g=!1;try{if(i=(r=r.call(e)).next,t!==0)for(;!(s=(n=i.call(r)).done)&&(c.push(n.value),c.length!==t);s=!0);}catch(_){g=!0,o=_}finally{try{if(!s&&r.return!=null&&(u=r.return(),Object(u)!==u))return}finally{if(g)throw o}}return c}}function De(){throw new TypeError(`Invalid attempt to destructure non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function le(e,t){var r=Object.keys(e);if(Object.getOwnPropertySymbols){var n=Object.getOwnPropertySymbols(e);t&&(n=n.filter(function(o){return Object.getOwnPropertyDescriptor(e,o).enumerable})),r.push.apply(r,n)}return r}function de(e){for(var t=1;t<arguments.length;t++){var r=arguments[t]!=null?arguments[t]:{};t%2?le(Object(r),!0).forEach(function(n){Te(e,n,r[n])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(r)):le(Object(r)).forEach(function(n){Object.defineProperty(e,n,Object.getOwnPropertyDescriptor(r,n))})}return e}function $e(e,t){if(e==null)return{};var r,n,o=ze(e,t);if(Object.getOwnPropertySymbols){var i=Object.getOwnPropertySymbols(e);for(n=0;n<i.length;n++)r=i[n],t.indexOf(r)===-1&&{}.propertyIsEnumerable.call(e,r)&&(o[r]=e[r])}return o}function ze(e,t){if(e==null)return{};var r={};for(var n in e)if({}.hasOwnProperty.call(e,n)){if(t.indexOf(n)!==-1)continue;r[n]=e[n]}return r}function He(e,t){return Ae(e)||Ie(e,t)||Be(e,t)||De()}function Ve(e,t){if(typeof e!="object"||!e)return e;var r=e[Symbol.toPrimitive];if(r!==void 0){var n=r.call(e,t);if(typeof n!="object")return n;throw new TypeError("@@toPrimitive must return a primitive value.")}return(t==="string"?String:Number)(e)}function We(e){var t=Ve(e,"string");return typeof t=="symbol"?t:t+""}function Be(e,t){if(e){if(typeof e=="string")return se(e,t);var r={}.toString.call(e).slice(8,-1);return r==="Object"&&e.constructor&&(r=e.constructor.name),r==="Map"||r==="Set"?Array.from(e):r==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(r)?se(e,t):void 0}}function Fe(e,t,r){return t in e?Object.defineProperty(e,t,{value:r,enumerable:!0,configurable:!0,writable:!0}):e[t]=r,e}function fe(e,t){var r=Object.keys(e);if(Object.getOwnPropertySymbols){var n=Object.getOwnPropertySymbols(e);t&&(n=n.filter(function(o){return Object.getOwnPropertyDescriptor(e,o).enumerable})),r.push.apply(r,n)}return r}function ge(e){for(var t=1;t<arguments.length;t++){var r=arguments[t]!=null?arguments[t]:{};t%2?fe(Object(r),!0).forEach(function(n){Fe(e,n,r[n])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(r)):fe(Object(r)).forEach(function(n){Object.defineProperty(e,n,Object.getOwnPropertyDescriptor(r,n))})}return e}function qe(){for(var e=arguments.length,t=new Array(e),r=0;r<e;r++)t[r]=arguments[r];return function(n){return t.reduceRight(function(o,i){return i(o)},n)}}function $(e){return function t(){for(var r=this,n=arguments.length,o=new Array(n),i=0;i<n;i++)o[i]=arguments[i];return o.length>=e.length?e.apply(this,o):function(){for(var u=arguments.length,c=new Array(u),s=0;s<u;s++)c[s]=arguments[s];return t.apply(r,[].concat(o,c))}}}function U(e){return{}.toString.call(e).includes("Object")}function Ue(e){return!Object.keys(e).length}function H(e){return typeof e=="function"}function Ke(e,t){return Object.prototype.hasOwnProperty.call(e,t)}function Ge(e,t){return U(t)||S("changeType"),Object.keys(t).some(function(r){return!Ke(e,r)})&&S("changeField"),t}function Ye(e){H(e)||S("selectorType")}function Je(e){H(e)||U(e)||S("handlerType"),U(e)&&Object.values(e).some(function(t){return!H(t)})&&S("handlersType")}function Xe(e){e||S("initialIsRequired"),U(e)||S("initialType"),Ue(e)&&S("initialContent")}function Ze(e,t){throw new Error(e[t]||e.default)}var Qe={initialIsRequired:"initial state is required",initialType:"initial state should be an object",initialContent:"initial state shouldn't be an empty object",handlerType:"handler should be an object or a function",handlersType:"all handlers should be a functions",selectorType:"selector should be a function",changeType:"provided value of changes should be an object",changeField:'it seams you want to change a field in the state which is not specified in the "initial" state',default:"an unknown error accured in `state-local` package"},S=$(Ze)(Qe),F={changes:Ge,selector:Ye,handler:Je,initial:Xe};function et(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{};F.initial(e),F.handler(t);var r={current:e},n=$(nt)(r,t),o=$(rt)(r),i=$(F.changes)(e),u=$(tt)(r);function c(){var g=arguments.length>0&&arguments[0]!==void 0?arguments[0]:function(_){return _};return F.selector(g),g(r.current)}function s(g){qe(n,o,i,u)(g)}return[c,s]}function tt(e,t){return H(t)?t(e.current):t}function rt(e,t){return e.current=ge(ge({},e.current),t),t}function nt(e,t,r){return H(t)?t(e.current):Object.keys(r).forEach(function(n){var o;return(o=t[n])===null||o===void 0?void 0:o.call(t,e.current[n])}),r}var ot={create:et},it={paths:{vs:"https://cdn.jsdelivr.net/npm/monaco-editor@0.54.0/min/vs"}};function at(e){return function t(){for(var r=this,n=arguments.length,o=new Array(n),i=0;i<n;i++)o[i]=arguments[i];return o.length>=e.length?e.apply(this,o):function(){for(var u=arguments.length,c=new Array(u),s=0;s<u;s++)c[s]=arguments[s];return t.apply(r,[].concat(o,c))}}}function ut(e){return{}.toString.call(e).includes("Object")}function ct(e){return e||me("configIsRequired"),ut(e)||me("configType"),e.urls?(st(),{paths:{vs:e.urls.monacoBase}}):e}function st(){console.warn(_e.deprecation)}function lt(e,t){throw new Error(e[t]||e.default)}var _e={configIsRequired:"the configuration object is required",configType:"the configuration object should be an object",default:"an unknown error accured in `@monaco-editor/loader` package",deprecation:`Deprecation warning!
    You are using deprecated way of configuration.

    Instead of using
      monaco.config({ urls: { monacoBase: '...' } })
    use
      monaco.config({ paths: { vs: '...' } })

    For more please check the link https://github.com/suren-atoyan/monaco-loader#config
  `},me=at(lt)(_e),dt={config:ct},ft=function(){for(var t=arguments.length,r=new Array(t),n=0;n<t;n++)r[n]=arguments[n];return function(o){return r.reduceRight(function(i,u){return u(i)},o)}};function ye(e,t){return Object.keys(t).forEach(function(r){t[r]instanceof Object&&e[r]&&Object.assign(t[r],ye(e[r],t[r]))}),de(de({},e),t)}var gt={type:"cancelation",msg:"operation is manually canceled"};function Q(e){var t=!1,r=new Promise(function(n,o){e.then(function(i){return t?o(gt):n(i)}),e.catch(o)});return r.cancel=function(){return t=!0},r}var mt=["monaco"],pt=ot.create({config:it,isInitialized:!1,resolve:null,reject:null,monaco:null}),Oe=He(pt,2),V=Oe[0],G=Oe[1];function ht(e){var t=dt.config(e),r=t.monaco,n=$e(t,mt);G(function(o){return{config:ye(o.config,n),monaco:r}})}function vt(){var e=V(function(t){var r=t.monaco,n=t.isInitialized,o=t.resolve;return{monaco:r,isInitialized:n,resolve:o}});if(!e.isInitialized){if(G({isInitialized:!0}),e.monaco)return e.resolve(e.monaco),Q(ee);if(window.monaco&&window.monaco.editor)return je(window.monaco),e.resolve(window.monaco),Q(ee);ft(bt,_t)(yt)}return Q(ee)}function bt(e){return document.body.appendChild(e)}function wt(e){var t=document.createElement("script");return e&&(t.src=e),t}function _t(e){var t=V(function(n){var o=n.config,i=n.reject;return{config:o,reject:i}}),r=wt("".concat(t.config.paths.vs,"/loader.js"));return r.onload=function(){return e()},r.onerror=t.reject,r}function yt(){var e=V(function(r){var n=r.config,o=r.resolve,i=r.reject;return{config:n,resolve:o,reject:i}}),t=window.require;t.config(e.config),t(["vs/editor/editor.main"],function(r){var n=r.m;je(n),e.resolve(n)},function(r){e.reject(r)})}function je(e){V().monaco||G({monaco:e})}function Ot(){return V(function(e){var t=e.monaco;return t})}var ee=new Promise(function(e,t){return G({resolve:e,reject:t})}),Ee={config:ht,init:vt,__getMonacoInstance:Ot},jt={wrapper:{display:"flex",position:"relative",textAlign:"initial"},fullWidth:{width:"100%"},hide:{display:"none"}},te=jt,Et={container:{display:"flex",height:"100%",width:"100%",justifyContent:"center",alignItems:"center"}},Mt=Et;function St({children:e}){return x.createElement("div",{style:Mt.container},e)}var Nt=St,kt=Nt;function Ct({width:e,height:t,isEditorReady:r,loading:n,_ref:o,className:i,wrapperProps:u}){return x.createElement("section",{style:{...te.wrapper,width:e,height:t},...u},!r&&x.createElement(kt,null,n),x.createElement("div",{ref:o,style:{...te.fullWidth,...!r&&te.hide},className:i}))}var Pt=Ct,Me=a.memo(Pt);function Rt(e){a.useEffect(e,[])}var Se=Rt;function xt(e,t,r=!0){let n=a.useRef(!0);a.useEffect(n.current||!r?()=>{n.current=!1}:e,t)}var j=xt;function z(){}function R(e,t,r,n){return Lt(e,n)||At(e,t,r,n)}function Lt(e,t){return e.editor.getModel(Ne(e,t))}function At(e,t,r,n){return e.editor.createModel(t,r,n?Ne(e,n):void 0)}function Ne(e,t){return e.Uri.parse(t)}function Tt({original:e,modified:t,language:r,originalLanguage:n,modifiedLanguage:o,originalModelPath:i,modifiedModelPath:u,keepCurrentOriginalModel:c=!1,keepCurrentModifiedModel:s=!1,theme:g="light",loading:_="Loading...",options:h={},height:E="100%",width:L="100%",className:k,wrapperProps:C={},beforeMount:A=z,onMount:T=z}){let[b,N]=a.useState(!1),[v,l]=a.useState(!0),m=a.useRef(null),p=a.useRef(null),I=a.useRef(null),y=a.useRef(T),d=a.useRef(A),P=a.useRef(!1);Se(()=>{let f=Ee.init();return f.then(w=>(p.current=w)&&l(!1)).catch(w=>w?.type!=="cancelation"&&console.error("Monaco initialization: error:",w)),()=>m.current?D():f.cancel()}),j(()=>{if(m.current&&p.current){let f=m.current.getOriginalEditor(),w=R(p.current,e||"",n||r||"text",i||"");w!==f.getModel()&&f.setModel(w)}},[i],b),j(()=>{if(m.current&&p.current){let f=m.current.getModifiedEditor(),w=R(p.current,t||"",o||r||"text",u||"");w!==f.getModel()&&f.setModel(w)}},[u],b),j(()=>{let f=m.current.getModifiedEditor();f.getOption(p.current.editor.EditorOption.readOnly)?f.setValue(t||""):t!==f.getValue()&&(f.executeEdits("",[{range:f.getModel().getFullModelRange(),text:t||"",forceMoveMarkers:!0}]),f.pushUndoStop())},[t],b),j(()=>{m.current?.getModel()?.original.setValue(e||"")},[e],b),j(()=>{let{original:f,modified:w}=m.current.getModel();p.current.editor.setModelLanguage(f,n||r||"text"),p.current.editor.setModelLanguage(w,o||r||"text")},[r,n,o],b),j(()=>{p.current?.editor.setTheme(g)},[g],b),j(()=>{m.current?.updateOptions(h)},[h],b);let W=a.useCallback(()=>{if(!p.current)return;d.current(p.current);let f=R(p.current,e||"",n||r||"text",i||""),w=R(p.current,t||"",o||r||"text",u||"");m.current?.setModel({original:f,modified:w})},[r,t,o,e,n,i,u]),B=a.useCallback(()=>{!P.current&&I.current&&(m.current=p.current.editor.createDiffEditor(I.current,{automaticLayout:!0,...h}),W(),p.current?.editor.setTheme(g),N(!0),P.current=!0)},[h,g,W]);a.useEffect(()=>{b&&y.current(m.current,p.current)},[b]),a.useEffect(()=>{!v&&!b&&B()},[v,b,B]);function D(){let f=m.current?.getModel();c||f?.original?.dispose(),s||f?.modified?.dispose(),m.current?.dispose()}return x.createElement(Me,{width:L,height:E,isEditorReady:b,loading:_,_ref:I,className:k,wrapperProps:C})}var It=Tt;a.memo(It);function Dt(e){let t=a.useRef();return a.useEffect(()=>{t.current=e},[e]),t.current}var $t=Dt,q=new Map;function zt({defaultValue:e,defaultLanguage:t,defaultPath:r,value:n,language:o,path:i,theme:u="light",line:c,loading:s="Loading...",options:g={},overrideServices:_={},saveViewState:h=!0,keepCurrentModel:E=!1,width:L="100%",height:k="100%",className:C,wrapperProps:A={},beforeMount:T=z,onMount:b=z,onChange:N,onValidate:v=z}){let[l,m]=a.useState(!1),[p,I]=a.useState(!0),y=a.useRef(null),d=a.useRef(null),P=a.useRef(null),W=a.useRef(b),B=a.useRef(T),D=a.useRef(),f=a.useRef(n),w=$t(i),ue=a.useRef(!1),Y=a.useRef(!1);Se(()=>{let O=Ee.init();return O.then(M=>(y.current=M)&&I(!1)).catch(M=>M?.type!=="cancelation"&&console.error("Monaco initialization: error:",M)),()=>d.current?xe():O.cancel()}),j(()=>{let O=R(y.current,e||n||"",t||o||"",i||r||"");O!==d.current?.getModel()&&(h&&q.set(w,d.current?.saveViewState()),d.current?.setModel(O),h&&d.current?.restoreViewState(q.get(i)))},[i],l),j(()=>{d.current?.updateOptions(g)},[g],l),j(()=>{!d.current||n===void 0||(d.current.getOption(y.current.editor.EditorOption.readOnly)?d.current.setValue(n):n!==d.current.getValue()&&(Y.current=!0,d.current.executeEdits("",[{range:d.current.getModel().getFullModelRange(),text:n,forceMoveMarkers:!0}]),d.current.pushUndoStop(),Y.current=!1))},[n],l),j(()=>{let O=d.current?.getModel();O&&o&&y.current?.editor.setModelLanguage(O,o)},[o],l),j(()=>{c!==void 0&&d.current?.revealLine(c)},[c],l),j(()=>{y.current?.editor.setTheme(u)},[u],l);let ce=a.useCallback(()=>{if(!(!P.current||!y.current)&&!ue.current){B.current(y.current);let O=i||r,M=R(y.current,n||e||"",t||o||"",O||"");d.current=y.current?.editor.create(P.current,{model:M,automaticLayout:!0,...g},_),h&&d.current.restoreViewState(q.get(O)),y.current.editor.setTheme(u),c!==void 0&&d.current.revealLine(c),m(!0),ue.current=!0}},[e,t,r,n,o,i,g,_,h,u,c]);a.useEffect(()=>{l&&W.current(d.current,y.current)},[l]),a.useEffect(()=>{!p&&!l&&ce()},[p,l,ce]),f.current=n,a.useEffect(()=>{l&&N&&(D.current?.dispose(),D.current=d.current?.onDidChangeModelContent(O=>{Y.current||N(d.current.getValue(),O)}))},[l,N]),a.useEffect(()=>{if(l){let O=y.current.editor.onDidChangeMarkers(M=>{let J=d.current.getModel()?.uri;if(J&&M.find(X=>X.path===J.path)){let X=y.current.editor.getModelMarkers({resource:J});v?.(X)}});return()=>{O?.dispose()}}return()=>{}},[l,v]);function xe(){D.current?.dispose(),E?h&&q.set(i,d.current.saveViewState()):d.current.getModel()?.dispose(),d.current.dispose()}return x.createElement(Me,{width:L,height:k,isEditorReady:l,loading:s,_ref:P,className:C,wrapperProps:A})}var Ht=zt,Vt=a.memo(Ht),Wt=Vt;const ke={kind:"row_detector",name:"detect_*",label:"ADE: row detector (detect_*)",signature:["def detect_*(","    *,","    run,","    state,","    row_index: int,","    row_values: list,","    logger,","    **_,",") -> float | dict:"].join(`
`),doc:"Row detector entrypoint: return tiny score deltas to help the engine classify streamed rows as header/data.",snippet:`
DEFAULT_LABEL = "\${1:header}"

def detect_\${2:name}(
    *,
    run,
    state,
    row_index: int,
    row_values: list,
    logger,
    **_,
) -> float | dict:
    """\${3:Explain what this detector scores.}"""
    score = 0.0
    # Return a float to apply to DEFAULT_LABEL, or a dict to touch multiple labels.
    return score
`.trim(),parameters:["run","state","row_index","row_values","logger"]},Ce={kind:"column_detector",name:"detect_*",label:"ADE: column detector (detect_*)",signature:["def detect_*(","    *,","    run,","    state,","    field_name: str,","    field_meta: dict,","    header: str | None,","    column_values_sample: list,","    column_values: tuple,","    table: dict,","    column_index: int,","    logger,","    **_,",") -> float | dict:"].join(`
`),doc:"Column detector entrypoint: score how likely the current raw column maps to this canonical field.",snippet:`
def detect_\${1:value_shape}(
    *,
    run,
    state,
    field_name: str,
    field_meta: dict,
    header: str | None,
    column_values_sample: list,
    column_values: tuple,
    table: dict,
    column_index: int,
    logger,
    **_,
) -> float | dict:
    """\${2:Describe your heuristic for this field.}"""
    score = 0.0
    # TODO: inspect header, column_values_sample, etc.
    return {field_name: score}
`.trim(),parameters:["run","state","field_name","field_meta","header","column_values_sample","column_values","table","column_index","logger"]},re={kind:"column_transform",name:"transform",label:"ADE: column transform",signature:["def transform(","    *,","    run,","    state,","    row_index: int,","    field_name: str,","    value,","    row: dict,","    logger,","    **_,",") -> dict | None:"].join(`
`),doc:"Column transform: normalize the mapped value or populate additional canonical fields for this row.",snippet:`
def transform(
    *,
    run,
    state,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    logger,
    **_,
) -> dict | None:
    """\${1:Normalize or expand the value for this row.}"""
    if value in (None, ""):
        return None
    normalized = value
    return {field_name: normalized}
`.trim(),parameters:["run","state","row_index","field_name","value","row","logger"]},ne={kind:"column_validator",name:"validate",label:"ADE: column validator",signature:["def validate(","    *,","    run,","    state,","    row_index: int,","    field_name: str,","    value,","    row: dict,","    field_meta: dict | None,","    logger,","    **_,",") -> list[dict]:"].join(`
`),doc:"Column validator: emit structured issues for the current row after transforms run.",snippet:`
def validate(
    *,
    run,
    state,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_meta: dict | None,
    logger,
    **_,
) -> list[dict]:
    """\${1:Return validation issues for this field/row.}"""
    issues: list[dict] = []
    if field_meta and field_meta.get("required") and value in (None, ""):
        issues.append({
            "row_index": row_index,
            "code": "required_missing",
            "severity": "error",
            "message": f"{field_name} is required.",
        })
    return issues
`.trim(),parameters:["run","state","row_index","field_name","value","row","field_meta","logger"]},pe={kind:"hook_on_run_start",name:"on_run_start",label:"ADE hook: on_run_start",signature:["def on_run_start(","    *,","    run_id: str,","    manifest: dict,","    env: dict | None = None,","    artifact: dict | None = None,","    logger=None,","    **_,",") -> None:"].join(`
`),doc:"Hook called once before detectors run. Use it for logging or lightweight setup.",snippet:`
def on_run_start(
    *,
    run_id: str,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    logger=None,
    **_,
) -> None:
    """\${1:Log or hydrate state before the run starts.}"""
    if logger:
        logger.info("run_start id=%s", run_id)
    return None
`.trim(),parameters:["run_id","manifest","env","artifact","logger"]},he={kind:"hook_after_mapping",name:"after_mapping",label:"ADE hook: after_mapping",signature:["def after_mapping(","    *,","    table: dict,","    manifest: dict,","    env: dict | None = None,","    logger=None,","    **_,",") -> dict:"].join(`
`),doc:"Hook to tweak the materialized table after column mapping but before transforms/validators.",snippet:`
def after_mapping(
    *,
    table: dict,
    manifest: dict,
    env: dict | None = None,
    logger=None,
    **_,
) -> dict:
    """\${1:Adjust headers/rows before transforms run.}"""
    # Example: rename a header
    table["headers"] = [h if h != "Work Email" else "Email" for h in table["headers"]]
    return table
`.trim(),parameters:["table","manifest","env","logger"]},ve={kind:"hook_before_save",name:"before_save",label:"ADE hook: before_save",signature:["def before_save(","    *,","    workbook,","    artifact: dict | None = None,","    logger=None,","    **_,",") -> object:"].join(`
`),doc:"Hook to polish the OpenPyXL workbook before it is written to disk.",snippet:`
def before_save(
    *,
    workbook,
    artifact: dict | None = None,
    logger=None,
    **_,
):
    """\${1:Style or summarize the workbook before it is saved.}"""
    ws = workbook.active
    ws.title = "Normalized"
    if logger:
        logger.info("before_save: rows=%s", ws.max_row)
    return workbook
`.trim(),parameters:["workbook","artifact","logger"]},be={kind:"hook_on_run_end",name:"on_run_end",label:"ADE hook: on_run_end",signature:["def on_run_end(","    *,","    artifact: dict | None = None,","    logger=None,","    **_,",") -> None:"].join(`
`),doc:"Hook called once after the run completes. Inspect the artifact for summary metrics.",snippet:`
def on_run_end(
    *,
    artifact: dict | None = None,
    logger=None,
    **_,
) -> None:
    """\${1:Log a completion summary.}"""
    if logger:
        total_sheets = len((artifact or {}).get("sheets", []))
        logger.info("run_end: sheets=%s", total_sheets)
    return None
`.trim(),parameters:["artifact","logger"]};function Bt(e){return e?e.replace(/\\/g,"/").toLowerCase():""}function oe(e){const t=Bt(e);return t.includes("/row_detectors/")?"row_detectors":t.includes("/column_detectors/")?"column_detectors":t.includes("/hooks/")?"hooks":"other"}function ie(e){return oe(e)!=="other"}const Pe=new Map([[pe.name,pe],[he.name,he],[ve.name,ve],[be.name,be]]);function Re(e,t){const r=oe(t);if(e){if(r==="row_detectors"&&e.startsWith("detect_"))return ke;if(r==="column_detectors"){if(e.startsWith("detect_"))return Ce;if(e===re.name)return re;if(e===ne.name)return ne}if(r==="hooks")return Pe.get(e)}}function Ft(e){const t=oe(e);return t==="row_detectors"?[ke]:t==="column_detectors"?[Ce,re,ne]:t==="hooks"?Array.from(Pe.values()):[]}const K=new Map;function qt(e,t="python"){const r=t||"python",n=K.get(r);if(n){n.refCount+=1;return}const o=[Kt(e,r),Gt(e,r),Yt(e,r)];K.set(r,{disposables:o,refCount:1})}function Ut(e="python"){const t=e||"python",r=K.get(t);r&&(r.refCount-=1,r.refCount<=0&&(r.disposables.forEach(n=>n.dispose()),K.delete(t)))}function Kt(e,t){return e.languages.registerHoverProvider(t,{provideHover(r,n){const o=ae(r);if(!ie(o))return null;const i=r.getWordAtPosition(n);if(!i)return null;const u=Re(i.word,o);return u?{range:new e.Range(n.lineNumber,i.startColumn,n.lineNumber,i.endColumn),contents:[{value:["```python",u.signature,"```"].join(`
`)},{value:u.doc}]}:null}})}function Gt(e,t){const r={suggestions:[]};return e.languages.registerCompletionItemProvider(t,{triggerCharacters:[" ","d","t","_"],provideCompletionItems(n,o){const i=ae(n);if(!ie(i))return r;const u=Ft(i);if(!u||u.length===0)return r;const c=o.lineNumber,s=n.getWordUntilPosition(o),g=s&&s.word?new e.Range(c,s.startColumn,c,s.endColumn):new e.Range(c,o.column,c,o.column);return{suggestions:u.map((h,E)=>Xt(e,h,g,E))}}})}function Yt(e,t){return e.languages.registerSignatureHelpProvider(t,{signatureHelpTriggerCharacters:["(",","],signatureHelpRetriggerCharacters:[","],provideSignatureHelp(r,n){const o=ae(r);if(!ie(o))return null;const u=r.getLineContent(n.lineNumber).slice(0,n.column),c=/([A-Za-z_][\w]*)\s*\($/.exec(u);if(!c)return null;const s=Re(c[1],o);if(!s)return null;const g=Jt(u),_=s.parameters.map(h=>({label:h}));return{value:{signatures:[{label:s.signature,documentation:s.doc,parameters:_}],activeSignature:0,activeParameter:Math.min(Math.max(g,0),Math.max(_.length-1,0))},dispose:()=>{}}}})}function ae(e){if(!e)return;const t=e.uri;if(!t)return;const r=t.path||t.toString();return r?r.startsWith("/")?r.slice(1):r:void 0}function Jt(e){const t=e.lastIndexOf("(");if(t===-1)return 0;const r=e.slice(t+1);return r.trim()?r.split(",").length-1:0}function Xt(e,t,r,n){return{label:t.label,kind:e.languages.CompletionItemKind.Snippet,insertText:t.snippet,insertTextRules:e.languages.CompletionItemInsertTextRule.InsertAsSnippet,documentation:{value:t.doc},detail:t.signature,range:r,sortText:`0${n}`}}const we="ade-dark",Zt={base:"vs-dark",inherit:!0,rules:[],colors:{"editor.background":"#1f2430","editor.foreground":"#f3f6ff","editorCursor.foreground":"#fbd38d","editor.lineHighlightBackground":"#2a3142","editorLineNumber.foreground":"#8c92a3","editor.selectionBackground":"#3a4256","editor.inactiveSelectionBackground":"#2d3446","editorGutter.background":"#1c212b"}},tr=a.forwardRef(function({value:t,onChange:r,language:n="plaintext",path:o,readOnly:i=!1,onSaveShortcut:u,className:c,theme:s=we},g){const _=a.useRef(u),h=a.useRef(null),E=a.useRef(null),L=a.useMemo(()=>Qt(o),[o]),k=a.useRef(null),[C,A]=a.useState(!1);a.useEffect(()=>{_.current=u},[u]);const T=a.useCallback(v=>{r(v??"")},[r]),b=a.useCallback((v,l)=>{const p=v.getModel()?.getLanguageId()??n;p==="python"&&(qt(l,p),E.current=p),v.addCommand(l.KeyMod.CtrlCmd|l.KeyCode.KeyS,()=>{_.current?.()}),h.current=v,A(!0)},[n]);a.useEffect(()=>()=>{E.current&&(Ut(E.current),E.current=null)},[]),a.useImperativeHandle(g,()=>({focus:()=>{h.current?.focus()},revealLine:v=>{const l=h.current;if(!l)return;const m=Math.max(1,Math.floor(v));l.revealLineInCenter(m),l.setPosition({lineNumber:m,column:1}),l.focus()}}),[]),a.useEffect(()=>{if(!C)return;const v=k.current;if(v&&typeof ResizeObserver<"u"){const m=new ResizeObserver(()=>{h.current?.layout()});return m.observe(v),h.current?.layout(),()=>m.disconnect()}const l=()=>h.current?.layout();return window.addEventListener("resize",l),l(),()=>window.removeEventListener("resize",l)},[C]),a.useEffect(()=>{const v=()=>h.current?.layout();return window.addEventListener("ade:workbench-layout",v),()=>window.removeEventListener("ade:workbench-layout",v)},[]);const N=a.useCallback(v=>{v.editor.defineTheme(we,Zt)},[]);return Z.jsx("div",{ref:k,className:Le("relative h-full w-full min-w-0 overflow-hidden",c),children:Z.jsx(Wt,{value:t,onChange:T,language:n,path:L,theme:s,beforeMount:N,height:"100%",width:"100%",options:{readOnly:i,minimap:{enabled:!1},fontSize:13,fontFamily:"'JetBrains Mono', 'Fira Code', 'Menlo', 'Monaco', monospace",scrollBeyondLastLine:!1,smoothScrolling:!0,automaticLayout:!0,lineNumbersMinChars:3,hover:{enabled:!0},wordBasedSuggestions:"currentDocument",quickSuggestions:{other:!0,comments:!1,strings:!0},suggestOnTriggerCharacters:!0,snippetSuggestions:"inline"},loading:Z.jsx("div",{className:"flex h-full items-center justify-center text-xs text-slate-400",children:"Loading editor…"}),onMount:b})})});function Qt(e){return e?e.includes("://")?e:`inmemory://ade/${e.startsWith("/")?e.slice(1):e}`:void 0}export{tr as default};
