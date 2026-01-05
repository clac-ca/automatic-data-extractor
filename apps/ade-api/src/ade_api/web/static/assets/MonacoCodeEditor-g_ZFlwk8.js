import{r as i,W as D,j as X,c as Re}from"./index-BnoesbUj.js";function me(e,t){(t==null||t>e.length)&&(t=e.length);for(var r=0,n=Array(t);r<t;r++)n[r]=e[r];return n}function Pe(e){if(Array.isArray(e))return e}function Ae(e,t,r){return(t=ze(t))in e?Object.defineProperty(e,t,{value:r,enumerable:!0,configurable:!0,writable:!0}):e[t]=r,e}function Te(e,t){var r=e==null?null:typeof Symbol<"u"&&e[Symbol.iterator]||e["@@iterator"];if(r!=null){var n,o,a,s,c=[],d=!0,g=!1;try{if(a=(r=r.call(e)).next,t!==0)for(;!(d=(n=a.call(r)).done)&&(c.push(n.value),c.length!==t);d=!0);}catch(_){g=!0,o=_}finally{try{if(!d&&r.return!=null&&(s=r.return(),Object(s)!==s))return}finally{if(g)throw o}}return c}}function De(){throw new TypeError(`Invalid attempt to destructure non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function ge(e,t){var r=Object.keys(e);if(Object.getOwnPropertySymbols){var n=Object.getOwnPropertySymbols(e);t&&(n=n.filter(function(o){return Object.getOwnPropertyDescriptor(e,o).enumerable})),r.push.apply(r,n)}return r}function pe(e){for(var t=1;t<arguments.length;t++){var r=arguments[t]!=null?arguments[t]:{};t%2?ge(Object(r),!0).forEach(function(n){Ae(e,n,r[n])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(r)):ge(Object(r)).forEach(function(n){Object.defineProperty(e,n,Object.getOwnPropertyDescriptor(r,n))})}return e}function Ie(e,t){if(e==null)return{};var r,n,o=$e(e,t);if(Object.getOwnPropertySymbols){var a=Object.getOwnPropertySymbols(e);for(n=0;n<a.length;n++)r=a[n],t.indexOf(r)===-1&&{}.propertyIsEnumerable.call(e,r)&&(o[r]=e[r])}return o}function $e(e,t){if(e==null)return{};var r={};for(var n in e)if({}.hasOwnProperty.call(e,n)){if(t.indexOf(n)!==-1)continue;r[n]=e[n]}return r}function Le(e,t){return Pe(e)||Te(e,t)||He(e,t)||De()}function We(e,t){if(typeof e!="object"||!e)return e;var r=e[Symbol.toPrimitive];if(r!==void 0){var n=r.call(e,t);if(typeof n!="object")return n;throw new TypeError("@@toPrimitive must return a primitive value.")}return(t==="string"?String:Number)(e)}function ze(e){var t=We(e,"string");return typeof t=="symbol"?t:t+""}function He(e,t){if(e){if(typeof e=="string")return me(e,t);var r={}.toString.call(e).slice(8,-1);return r==="Object"&&e.constructor&&(r=e.constructor.name),r==="Map"||r==="Set"?Array.from(e):r==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(r)?me(e,t):void 0}}function Be(e,t,r){return t in e?Object.defineProperty(e,t,{value:r,enumerable:!0,configurable:!0,writable:!0}):e[t]=r,e}function he(e,t){var r=Object.keys(e);if(Object.getOwnPropertySymbols){var n=Object.getOwnPropertySymbols(e);t&&(n=n.filter(function(o){return Object.getOwnPropertyDescriptor(e,o).enumerable})),r.push.apply(r,n)}return r}function _e(e){for(var t=1;t<arguments.length;t++){var r=arguments[t]!=null?arguments[t]:{};t%2?he(Object(r),!0).forEach(function(n){Be(e,n,r[n])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(r)):he(Object(r)).forEach(function(n){Object.defineProperty(e,n,Object.getOwnPropertyDescriptor(r,n))})}return e}function Ve(){for(var e=arguments.length,t=new Array(e),r=0;r<e;r++)t[r]=arguments[r];return function(n){return t.reduceRight(function(o,a){return a(o)},n)}}function L(e){return function t(){for(var r=this,n=arguments.length,o=new Array(n),a=0;a<n;a++)o[a]=arguments[a];return o.length>=e.length?e.apply(this,o):function(){for(var s=arguments.length,c=new Array(s),d=0;d<s;d++)c[d]=arguments[d];return t.apply(r,[].concat(o,c))}}}function U(e){return{}.toString.call(e).includes("Object")}function Ke(e){return!Object.keys(e).length}function z(e){return typeof e=="function"}function Fe(e,t){return Object.prototype.hasOwnProperty.call(e,t)}function qe(e,t){return U(t)||O("changeType"),Object.keys(t).some(function(r){return!Fe(e,r)})&&O("changeField"),t}function Ue(e){z(e)||O("selectorType")}function Ze(e){z(e)||U(e)||O("handlerType"),U(e)&&Object.values(e).some(function(t){return!z(t)})&&O("handlersType")}function Ge(e){e||O("initialIsRequired"),U(e)||O("initialType"),Ke(e)&&O("initialContent")}function Ye(e,t){throw new Error(e[t]||e.default)}var Je={initialIsRequired:"initial state is required",initialType:"initial state should be an object",initialContent:"initial state shouldn't be an empty object",handlerType:"handler should be an object or a function",handlersType:"all handlers should be a functions",selectorType:"selector should be a function",changeType:"provided value of changes should be an object",changeField:'it seams you want to change a field in the state which is not specified in the "initial" state',default:"an unknown error accured in `state-local` package"},O=L(Ye)(Je),K={changes:qe,selector:Ue,handler:Ze,initial:Ge};function Qe(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{};K.initial(e),K.handler(t);var r={current:e},n=L(tt)(r,t),o=L(et)(r),a=L(K.changes)(e),s=L(Xe)(r);function c(){var g=arguments.length>0&&arguments[0]!==void 0?arguments[0]:function(_){return _};return K.selector(g),g(r.current)}function d(g){Ve(n,o,a,s)(g)}return[c,d]}function Xe(e,t){return z(t)?t(e.current):t}function et(e,t){return e.current=_e(_e({},e.current),t),t}function tt(e,t,r){return z(t)?t(e.current):Object.keys(r).forEach(function(n){var o;return(o=t[n])===null||o===void 0?void 0:o.call(t,e.current[n])}),r}var rt={create:Qe},nt={paths:{vs:"https://cdn.jsdelivr.net/npm/monaco-editor@0.54.0/min/vs"}};function ot(e){return function t(){for(var r=this,n=arguments.length,o=new Array(n),a=0;a<n;a++)o[a]=arguments[a];return o.length>=e.length?e.apply(this,o):function(){for(var s=arguments.length,c=new Array(s),d=0;d<s;d++)c[d]=arguments[d];return t.apply(r,[].concat(o,c))}}}function at(e){return{}.toString.call(e).includes("Object")}function it(e){return e||be("configIsRequired"),at(e)||be("configType"),e.urls?(st(),{paths:{vs:e.urls.monacoBase}}):e}function st(){console.warn(we.deprecation)}function ut(e,t){throw new Error(e[t]||e.default)}var we={configIsRequired:"the configuration object is required",configType:"the configuration object should be an object",default:"an unknown error accured in `@monaco-editor/loader` package",deprecation:`Deprecation warning!
    You are using deprecated way of configuration.

    Instead of using
      monaco.config({ urls: { monacoBase: '...' } })
    use
      monaco.config({ paths: { vs: '...' } })

    For more please check the link https://github.com/suren-atoyan/monaco-loader#config
  `},be=ot(ut)(we),ct={config:it},lt=function(){for(var t=arguments.length,r=new Array(t),n=0;n<t;n++)r[n]=arguments[n];return function(o){return r.reduceRight(function(a,s){return s(a)},o)}};function ke(e,t){return Object.keys(t).forEach(function(r){t[r]instanceof Object&&e[r]&&Object.assign(t[r],ke(e[r],t[r]))}),pe(pe({},e),t)}var dt={type:"cancelation",msg:"operation is manually canceled"};function ee(e){var t=!1,r=new Promise(function(n,o){e.then(function(a){return t?o(dt):n(a)}),e.catch(o)});return r.cancel=function(){return t=!0},r}var ft=["monaco"],mt=rt.create({config:nt,isInitialized:!1,resolve:null,reject:null,monaco:null}),ye=Le(mt,2),H=ye[0],G=ye[1];function gt(e){var t=ct.config(e),r=t.monaco,n=Ie(t,ft);G(function(o){return{config:ke(o.config,n),monaco:r}})}function pt(){var e=H(function(t){var r=t.monaco,n=t.isInitialized,o=t.resolve;return{monaco:r,isInitialized:n,resolve:o}});if(!e.isInitialized){if(G({isInitialized:!0}),e.monaco)return e.resolve(e.monaco),ee(te);if(window.monaco&&window.monaco.editor)return Ne(window.monaco),e.resolve(window.monaco),ee(te);lt(ht,bt)(vt)}return ee(te)}function ht(e){return document.body.appendChild(e)}function _t(e){var t=document.createElement("script");return e&&(t.src=e),t}function bt(e){var t=H(function(n){var o=n.config,a=n.reject;return{config:o,reject:a}}),r=_t("".concat(t.config.paths.vs,"/loader.js"));return r.onload=function(){return e()},r.onerror=t.reject,r}function vt(){var e=H(function(r){var n=r.config,o=r.resolve,a=r.reject;return{config:n,resolve:o,reject:a}}),t=window.require;t.config(e.config),t(["vs/editor/editor.main"],function(r){var n=r.m;Ne(n),e.resolve(n)},function(r){e.reject(r)})}function Ne(e){H().monaco||G({monaco:e})}function wt(){return H(function(e){var t=e.monaco;return t})}var te=new Promise(function(e,t){return G({resolve:e,reject:t})}),Se={config:gt,init:pt,__getMonacoInstance:wt},kt={wrapper:{display:"flex",position:"relative",textAlign:"initial"},fullWidth:{width:"100%"},hide:{display:"none"}},re=kt,yt={container:{display:"flex",height:"100%",width:"100%",justifyContent:"center",alignItems:"center"}},Nt=yt;function St({children:e}){return D.createElement("div",{style:Nt.container},e)}var jt=St,Mt=jt;function Et({width:e,height:t,isEditorReady:r,loading:n,_ref:o,className:a,wrapperProps:s}){return D.createElement("section",{style:{...re.wrapper,width:e,height:t},...s},!r&&D.createElement(Mt,null,n),D.createElement("div",{ref:o,style:{...re.fullWidth,...!r&&re.hide},className:a}))}var Ot=Et,je=i.memo(Ot);function Ct(e){i.useEffect(e,[])}var Me=Ct;function xt(e,t,r=!0){let n=i.useRef(!0);i.useEffect(n.current||!r?()=>{n.current=!1}:e,t)}var y=xt;function W(){}function T(e,t,r,n){return Rt(e,n)||Pt(e,t,r,n)}function Rt(e,t){return e.editor.getModel(Ee(e,t))}function Pt(e,t,r,n){return e.editor.createModel(t,r,n?Ee(e,n):void 0)}function Ee(e,t){return e.Uri.parse(t)}function At({original:e,modified:t,language:r,originalLanguage:n,modifiedLanguage:o,originalModelPath:a,modifiedModelPath:s,keepCurrentOriginalModel:c=!1,keepCurrentModifiedModel:d=!1,theme:g="light",loading:_="Loading...",options:h={},height:N="100%",width:R="100%",className:j,wrapperProps:M={},beforeMount:P=W,onMount:I=W}){let[b,C]=i.useState(!1),[x,u]=i.useState(!0),l=i.useRef(null),m=i.useRef(null),S=i.useRef(null),w=i.useRef(I),f=i.useRef(P),A=i.useRef(!1);Me(()=>{let p=Se.init();return p.then(v=>(m.current=v)&&u(!1)).catch(v=>v?.type!=="cancelation"&&console.error("Monaco initialization: error:",v)),()=>l.current?$():p.cancel()}),y(()=>{if(l.current&&m.current){let p=l.current.getOriginalEditor(),v=T(m.current,e||"",n||r||"text",a||"");v!==p.getModel()&&p.setModel(v)}},[a],b),y(()=>{if(l.current&&m.current){let p=l.current.getModifiedEditor(),v=T(m.current,t||"",o||r||"text",s||"");v!==p.getModel()&&p.setModel(v)}},[s],b),y(()=>{let p=l.current.getModifiedEditor();p.getOption(m.current.editor.EditorOption.readOnly)?p.setValue(t||""):t!==p.getValue()&&(p.executeEdits("",[{range:p.getModel().getFullModelRange(),text:t||"",forceMoveMarkers:!0}]),p.pushUndoStop())},[t],b),y(()=>{l.current?.getModel()?.original.setValue(e||"")},[e],b),y(()=>{let{original:p,modified:v}=l.current.getModel();m.current.editor.setModelLanguage(p,n||r||"text"),m.current.editor.setModelLanguage(v,o||r||"text")},[r,n,o],b),y(()=>{m.current?.editor.setTheme(g)},[g],b),y(()=>{l.current?.updateOptions(h)},[h],b);let B=i.useCallback(()=>{if(!m.current)return;f.current(m.current);let p=T(m.current,e||"",n||r||"text",a||""),v=T(m.current,t||"",o||r||"text",s||"");l.current?.setModel({original:p,modified:v})},[r,t,o,e,n,a,s]),V=i.useCallback(()=>{!A.current&&S.current&&(l.current=m.current.editor.createDiffEditor(S.current,{automaticLayout:!0,...h}),B(),m.current?.editor.setTheme(g),C(!0),A.current=!0)},[h,g,B]);i.useEffect(()=>{b&&w.current(l.current,m.current)},[b]),i.useEffect(()=>{!x&&!b&&V()},[x,b,V]);function $(){let p=l.current?.getModel();c||p?.original?.dispose(),d||p?.modified?.dispose(),l.current?.dispose()}return D.createElement(je,{width:R,height:N,isEditorReady:b,loading:_,_ref:S,className:j,wrapperProps:M})}var Tt=At;i.memo(Tt);function Dt(e){let t=i.useRef();return i.useEffect(()=>{t.current=e},[e]),t.current}var It=Dt,F=new Map;function $t({defaultValue:e,defaultLanguage:t,defaultPath:r,value:n,language:o,path:a,theme:s="light",line:c,loading:d="Loading...",options:g={},overrideServices:_={},saveViewState:h=!0,keepCurrentModel:N=!1,width:R="100%",height:j="100%",className:M,wrapperProps:P={},beforeMount:I=W,onMount:b=W,onChange:C,onValidate:x=W}){let[u,l]=i.useState(!1),[m,S]=i.useState(!0),w=i.useRef(null),f=i.useRef(null),A=i.useRef(null),B=i.useRef(b),V=i.useRef(I),$=i.useRef(),p=i.useRef(n),v=It(a),de=i.useRef(!1),Y=i.useRef(!1);Me(()=>{let k=Se.init();return k.then(E=>(w.current=E)&&S(!1)).catch(E=>E?.type!=="cancelation"&&console.error("Monaco initialization: error:",E)),()=>f.current?xe():k.cancel()}),y(()=>{let k=T(w.current,e||n||"",t||o||"",a||r||"");k!==f.current?.getModel()&&(h&&F.set(v,f.current?.saveViewState()),f.current?.setModel(k),h&&f.current?.restoreViewState(F.get(a)))},[a],u),y(()=>{f.current?.updateOptions(g)},[g],u),y(()=>{!f.current||n===void 0||(f.current.getOption(w.current.editor.EditorOption.readOnly)?f.current.setValue(n):n!==f.current.getValue()&&(Y.current=!0,f.current.executeEdits("",[{range:f.current.getModel().getFullModelRange(),text:n,forceMoveMarkers:!0}]),f.current.pushUndoStop(),Y.current=!1))},[n],u),y(()=>{let k=f.current?.getModel();k&&o&&w.current?.editor.setModelLanguage(k,o)},[o],u),y(()=>{c!==void 0&&f.current?.revealLine(c)},[c],u),y(()=>{w.current?.editor.setTheme(s)},[s],u);let fe=i.useCallback(()=>{if(!(!A.current||!w.current)&&!de.current){V.current(w.current);let k=a||r,E=T(w.current,n||e||"",t||o||"",k||"");f.current=w.current?.editor.create(A.current,{model:E,automaticLayout:!0,...g},_),h&&f.current.restoreViewState(F.get(k)),w.current.editor.setTheme(s),c!==void 0&&f.current.revealLine(c),l(!0),de.current=!0}},[e,t,r,n,o,a,g,_,h,s,c]);i.useEffect(()=>{u&&B.current(f.current,w.current)},[u]),i.useEffect(()=>{!m&&!u&&fe()},[m,u,fe]),p.current=n,i.useEffect(()=>{u&&C&&($.current?.dispose(),$.current=f.current?.onDidChangeModelContent(k=>{Y.current||C(f.current.getValue(),k)}))},[u,C]),i.useEffect(()=>{if(u){let k=w.current.editor.onDidChangeMarkers(E=>{let J=f.current.getModel()?.uri;if(J&&E.find(Q=>Q.path===J.path)){let Q=w.current.editor.getModelMarkers({resource:J});x?.(Q)}});return()=>{k?.dispose()}}return()=>{}},[u,x]);function xe(){$.current?.dispose(),N?h&&F.set(a,f.current.saveViewState()):f.current.getModel()?.dispose(),f.current.dispose()}return D.createElement(je,{width:R,height:j,isEditorReady:u,loading:d,_ref:A,className:M,wrapperProps:P})}var Lt=$t,Wt=i.memo(Lt),zt=Wt;function Ht(e){return new Worker("/assets/editor.worker-B4pQIWZD.js",{name:e?.name})}function Bt(e){return new Worker("/assets/css.worker-DbrSMjj7.js",{name:e?.name})}function Vt(e){return new Worker("/assets/html.worker-Dy32WPZk.js",{name:e?.name})}function Kt(e){return new Worker("/assets/json.worker-jwAog0-I.js",{name:e?.name})}function Ft(e){return new Worker("/assets/ts.worker-B30KKKSO.js",{name:e?.name})}const qt={kind:"row_detector",name:"detect_*",label:"ADE: row detector (detect_*)",signature:["def detect_*(","    *,","    row_index: int,","    row_values: list,","    sheet_name: str | None,","    metadata: dict | None,","    state: dict,","    input_file_name: str | None,","    logger,","    **_,",") -> dict[str, float] | None:"].join(`
`),doc:"Row detector entrypoint: vote for row kinds (e.g., header vs data). Return a mapping of RowKind→score deltas or None.",snippet:`
def detect_\${2:name}(
    *,
    row_index: int,
    row_values: list,
    sheet_name: str | None,
    metadata: dict | None,
    state: dict,
    input_file_name: str | None,
    logger,
    **_,
) -> dict[str, float] | None:
    """\${3:Explain what this detector scores.}"""
    values = row_values or []
    non_empty = [v for v in values if v not in (None, "") and not (isinstance(v, str) and not v.strip())]
    density = len(non_empty) / max(len(values), 1) if values else 0.0
    score = min(1.0, density)
    return {"data": score, "header": -score * 0.2}
`.trim(),parameters:["row_index","row_values","sheet_name","metadata","state","input_file_name","logger"]},Oe={kind:"column_detector",name:"detect_*",label:"ADE: column detector (detect_*)",signature:["def detect_*(","    *,","    column_index: int,","    header,","    values,","    values_sample,","    sheet_name: str | None,","    metadata: dict | None,","    state: dict,","    input_file_name: str | None,","    logger,","    **_,",") -> dict[str, float] | None:"].join(`
`),doc:"Column detector entrypoint: score how likely the current raw column maps to a canonical field.",snippet:`
def detect_\${1:value_shape}(
    *,
    column_index: int,
    header,
    values,
    values_sample,
    sheet_name: str | None,
    metadata: dict | None,
    state: dict,
    input_file_name: str | None,
    logger,
    **_,
) -> dict[str, float] | None:
    """\${2:Describe your heuristic for this field.}"""
    target_field = "\${3:field_name}"
    header_text = "" if header is None else str(header).strip().lower()
    if not header_text:
        return None
    if target_field.replace("_", " ") in header_text:
        return {target_field: 1.0}
    return None
`.trim(),parameters:["column_index","header","values","values_sample","sheet_name","metadata","state","input_file_name","logger"]},ne={kind:"column_transform",name:"transform",label:"ADE: column transform",signature:["def transform(","    *,","    field_name: str,","    values,","    mapping,","    state: dict,","    metadata: dict | None,","    input_file_name: str | None,","    logger,","    **_,",") -> list[dict]:"].join(`
`),doc:"Column transform: normalize column values and emit row-indexed results. Return a list of {row_index, value}.",snippet:`
def transform(
    *,
    field_name: str,
    values,
    mapping,
    state: dict,
    metadata: dict | None,
    input_file_name: str | None,
    logger,
    **_,
) -> list[dict]:
    """\${1:Normalize or expand the values for this column.}"""
    results: list[dict] = []
    for idx, value in enumerate(values):
        text = "" if value is None else str(value).strip()
        normalized = text.title() if text else None
        results.append({"row_index": idx, "value": {field_name: normalized}})
    return results
`.trim(),parameters:["field_name","values","mapping","state","metadata","input_file_name","logger"]},oe={kind:"column_validator",name:"validate",label:"ADE: column validator",signature:["def validate(","    *,","    field_name: str,","    values,","    mapping,","    state: dict,","    metadata: dict | None,","    column_index: int,","    input_file_name: str | None,","    logger,","    **_,",") -> list[dict]:"].join(`
`),doc:"Column validator: emit structured issues for a column. Return a list of {row_index, message, ...}.",snippet:`
def validate(
    *,
    field_name: str,
    values,
    mapping,
    state: dict,
    metadata: dict | None,
    column_index: int,
    input_file_name: str | None,
    logger,
    **_,
) -> list[dict]:
    """\${1:Return validation issues for this column.}"""
    issues: list[dict] = []
    for idx, value in enumerate(values):
        text = "" if value is None else str(value).strip()
        if metadata and metadata.get("required") and not text:
            issues.append({"row_index": idx, "message": f"{field_name} is required"})
        # Add custom checks here (e.g., regex, enum membership).
    return issues
`.trim(),parameters:["field_name","values","mapping","state","metadata","column_index","input_file_name","logger"]},ae={kind:"hook_workbook_start",name:"on_workbook_start",label:"ADE hook: on_workbook_start",signature:["def on_workbook_start(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called once per workbook before any sheets/tables are processed.",snippet:`
def on_workbook_start(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Seed shared state or log workbook info.}"""
    state.setdefault("notes", [])
    if logger:
        logger.info("workbook start: %s", input_file_name or "")
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},ie={kind:"hook_sheet_start",name:"on_sheet_start",label:"ADE hook: on_sheet_start",signature:["def on_sheet_start(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called when a sheet is selected for processing (before detectors run).",snippet:`
def on_sheet_start(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Sheet-level logging or state init.}"""
    if logger and sheet:
        logger.info("sheet start: %s", getattr(sheet, "title", ""))
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},se={kind:"hook_table_detected",name:"on_table_detected",label:"ADE hook: on_table_detected",signature:["def on_table_detected(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called after a table is detected. Inspect table metadata or log.",snippet:`
def on_table_detected(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Log detection details or tweak state.}"""
    if logger and table:
        logger.info("table detected: sheet=%s header_row=%s", getattr(table, "sheet_name", ""), getattr(table, "header_row_index", None))
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},ue={kind:"hook_table_mapped",name:"on_table_mapped",label:"ADE hook: on_table_mapped",signature:["def on_table_mapped(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> dict | None:"].join(`
`),doc:"Called after mapping; return a ColumnMappingPatch or None.",snippet:`
def on_table_mapped(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> dict | None:
    """\${1:Propose mapping tweaks or log detected fields.}"""
    if logger and table:
        detected_fields = [col.field_name for col in getattr(table, "mapped_columns", [])]
        logger.info("table mapped (detected_fields=%s)", detected_fields)
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},ce={kind:"hook_table_written",name:"on_table_written",label:"ADE hook: on_table_written",signature:["def on_table_written(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called after a table is written to the output workbook.",snippet:`
def on_table_written(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Finalize sheet formatting or log counts.}"""
    if logger and table:
        logger.info("table written rows=%s", len(getattr(table, "rows", []) or []))
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},le={kind:"hook_workbook_before_save",name:"on_workbook_before_save",label:"ADE hook: on_workbook_before_save",signature:["def on_workbook_before_save(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called once before the output workbook is saved to disk.",snippet:`
def on_workbook_before_save(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Style workbook or attach summaries before save.}"""
    if logger:
        logger.info("workbook before save: %s", input_file_name or "")
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},Ut=[qt,Oe,ne,oe,ae,ie,se,ue,ce,le],Zt=new Map([[ae.name,ae],[ie.name,ie],[se.name,se],[ue.name,ue],[ce.name,ce],[le.name,le]]);function Ce(e){if(e)return e.startsWith("detect_")?Oe:e===ne.name?ne:e===oe.name?oe:Zt.get(e)}function Gt(){return Ut}const Z=new Map;function Yt(e,t="python"){const r=t||"python",n=Z.get(r);if(n){n.refCount+=1;return}const o=[Qt(e,r),Xt(e,r),er(e,r)];Z.set(r,{disposables:o,refCount:1})}function Jt(e="python"){const t=e||"python",r=Z.get(t);r&&(r.refCount-=1,r.refCount<=0&&(r.disposables.forEach(n=>n.dispose()),Z.delete(t)))}function Qt(e,t){return e.languages.registerHoverProvider(t,{provideHover(r,n){const o=r.getWordAtPosition(n);if(!o)return null;const a=Ce(o.word);return a?{range:new e.Range(n.lineNumber,o.startColumn,n.lineNumber,o.endColumn),contents:[{value:["```python",a.signature,"```"].join(`
`)},{value:a.doc}]}:null}})}function Xt(e,t){const r={suggestions:[]};return e.languages.registerCompletionItemProvider(t,{triggerCharacters:[" ","d","t","_"],provideCompletionItems(n,o){const a=Gt();if(!a||a.length===0)return r;const s=o.lineNumber,c=n.getValueInRange(new e.Range(s,1,s,o.column)),d=c.replace(/\s+$/,""),g=c.length-d.length,_=/[A-Za-z_][\w]*$/.exec(d),h=_?o.column-g-_[0].length:o.column-g,N=new e.Range(s,Math.max(1,h),s,o.column);return{suggestions:a.map((j,M)=>rr(e,j,N,M))}}})}function er(e,t){return e.languages.registerSignatureHelpProvider(t,{signatureHelpTriggerCharacters:["(",","],signatureHelpRetriggerCharacters:[","],provideSignatureHelp(r,n){const a=r.getLineContent(n.lineNumber).slice(0,n.column),s=/([A-Za-z_][\w]*)\s*\($/.exec(a);if(!s)return null;const c=Ce(s[1]);if(!c)return null;const d=tr(a),g=c.parameters.map(_=>({label:_}));return{value:{signatures:[{label:c.signature,documentation:c.doc,parameters:g}],activeSignature:0,activeParameter:Math.min(Math.max(d,0),Math.max(g.length-1,0))},dispose:()=>{}}}})}function tr(e){const t=e.lastIndexOf("(");if(t===-1)return 0;const r=e.slice(t+1);return r.trim()?r.split(",").length-1:0}function rr(e,t,r,n){return{label:t.label,kind:e.languages.CompletionItemKind.Snippet,insertText:t.snippet,insertTextRules:e.languages.CompletionItemInsertTextRule.InsertAsSnippet,documentation:{value:t.doc},detail:t.signature,range:r,sortText:`0${n}`}}const q="ade-dark",nr={"editor.background":"#1f2430","editor.foreground":"#f3f6ff","editorCursor.foreground":"#fbd38d","editor.lineHighlightBackground":"#2a3142","editorLineNumber.foreground":"#8c92a3","editor.selectionBackground":"#3a4256","editor.inactiveSelectionBackground":"#2d3446","editorGutter.background":"#1c212b"},or={"editor.background":"--comp-editor-bg","editor.foreground":"--comp-editor-fg","editorCursor.foreground":"--comp-editor-cursor","editor.lineHighlightBackground":"--comp-editor-line-highlight","editorLineNumber.foreground":"--comp-editor-line-number","editor.selectionBackground":"--comp-editor-selection","editor.inactiveSelectionBackground":"--comp-editor-selection-inactive","editorGutter.background":"--comp-editor-gutter"},lr=i.forwardRef(function({value:t,onChange:r,language:n="plaintext",path:o,readOnly:a=!1,onSaveShortcut:s,className:c,theme:d=q},g){const _=i.useRef(s),h=i.useRef(null),N=i.useRef(null),R=i.useMemo(()=>ar(o),[o]),j=i.useRef(null),M=i.useRef(null),[P,I]=i.useState(!1);i.useEffect(()=>{_.current=s},[s]);const b=i.useCallback(u=>{r(u??"")},[r]),C=i.useCallback((u,l)=>{const S=u.getModel()?.getLanguageId()??n;S==="python"&&(Yt(l,S),N.current=S),u.addCommand(l.KeyMod.CtrlCmd|l.KeyCode.KeyS,()=>{_.current?.()}),h.current=u,I(!0)},[n]);i.useEffect(()=>()=>{N.current&&(Jt(N.current),N.current=null)},[]),i.useImperativeHandle(g,()=>({focus:()=>{h.current?.focus()},revealLine:u=>{const l=h.current;if(!l)return;const m=Math.max(1,Math.floor(u));l.revealLineInCenter(m),l.setPosition({lineNumber:m,column:1}),l.focus()}}),[]),i.useEffect(()=>{if(!P)return;const u=j.current;if(u&&typeof ResizeObserver<"u"){const m=new ResizeObserver(()=>{h.current?.layout()});return m.observe(u),h.current?.layout(),()=>m.disconnect()}const l=()=>h.current?.layout();return window.addEventListener("resize",l),l(),()=>window.removeEventListener("resize",l)},[P]),i.useEffect(()=>{const u=()=>h.current?.layout();return window.addEventListener("ade:workbench-layout",u),()=>window.removeEventListener("ade:workbench-layout",u)},[]);const x=i.useCallback(u=>{ir(),M.current=u,u.editor.defineTheme(q,ve())},[]);return i.useEffect(()=>{if(d!==q)return;const u=M.current;u&&u.editor.defineTheme(q,ve())},[d]),X.jsx("div",{ref:j,className:Re("relative h-full w-full min-w-0 overflow-hidden",c),children:X.jsx(zt,{value:t,onChange:b,language:n,path:R,theme:d,beforeMount:x,height:"100%",width:"100%",options:{readOnly:a,minimap:{enabled:!1},fontSize:13,fontFamily:"'JetBrains Mono', 'Fira Code', 'Menlo', 'Monaco', monospace",scrollBeyondLastLine:!1,smoothScrolling:!0,automaticLayout:!0,lineNumbersMinChars:3,hover:{enabled:!0},wordBasedSuggestions:"currentDocument",quickSuggestions:{other:!0,comments:!1,strings:!0},suggestOnTriggerCharacters:!0,snippetSuggestions:"inline"},loading:X.jsx("div",{className:"flex h-full items-center justify-center text-xs text-muted-foreground",children:"Loading editor…"}),onMount:C})})});function ar(e){return e?e.includes("://")?e:`inmemory://ade/${e.startsWith("/")?e.slice(1):e}`:void 0}function ir(){const e=globalThis;e.MonacoEnvironment?.getWorker||(e.MonacoEnvironment={getWorker:(t,r)=>{switch(r){case"json":return new Kt;case"css":case"less":case"scss":return new Bt;case"html":case"handlebars":case"razor":return new Vt;case"typescript":case"javascript":return new Ft;default:return new Ht}}})}function ve(){const e={};return Object.entries(or).forEach(([t,r])=>{e[t]=sr(r,nr[t])}),{base:"vs-dark",inherit:!0,rules:[],colors:e}}function sr(e,t){if(typeof window>"u"||typeof document>"u")return t;const r=getComputedStyle(document.documentElement).getPropertyValue(e).trim();if(!r)return t;const n=r.split(/[\s,]+/).map(o=>Number(o)).filter(o=>Number.isFinite(o));return n.length<3?t:ur(n[0],n[1],n[2])}function ur(e,t,r){const n=o=>Math.max(0,Math.min(255,Math.round(o))).toString(16).padStart(2,"0");return`#${n(e)}${n(t)}${n(r)}`}export{lr as default};
