#!/usr/bin/env python3
import argparse, json, os, sys, glob, yaml
from collections import defaultdict

def load_objects(args):
    objs = []
    if args.json:
        with open(args.json) as f:
            data = json.load(f)
        items = data.get("items", [])
        if items:
            objs.extend(items)
        else:
            # single object json
            objs.append(data)
    if args.yaml:
        with open(args.yaml) as f:
            for doc in yaml.safe_load_all(f):
                if doc:
                    objs.append(doc)
    if args.dir:
        for path in glob.glob(os.path.join(args.dir, "*.y*ml")):
            with open(path) as f:
                for doc in yaml.safe_load_all(f):
                    if doc:
                        objs.append(doc)
    # normalize: ensure required fields
    norm = []
    for o in objs:
        if not isinstance(o, dict): continue
        if "kind" in o and "metadata" in o:
            norm.append(o)
    return norm

def ns(obj): return obj.get("metadata", {}).get("namespace", "default")
def name(obj): return obj.get("metadata", {}).get("name", "")
def kind(obj): return obj.get("kind", "")

def label_map(obj): return obj.get("metadata", {}).get("labels", {}) or {}
def selector_map(obj):
    sel = obj.get("spec", {}).get("selector", {})
    if isinstance(sel, dict):
        # deployments have .spec.selector.matchLabels
        return sel.get("matchLabels", sel) or {}
    return {}

def svc_selector(obj):
    sel = obj.get("spec", {}).get("selector", {})
    return sel or {}

def workload_type(k):
    return k in ("Deployment","StatefulSet","DaemonSet","Job","CronJob")

def obj_key(obj): return f"{ns(obj)}:{kind(obj)}:{name(obj)}"

def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--json", help="kubectl get ... -o json")
    src.add_argument("--yaml", help="helm template output or multi-doc yaml")
    src.add_argument("--dir",  help="directory with yaml manifests")
    ap.add_argument("--outdir", default="diagrams", help="output folder")
    ap.add_argument("--include-pods", action="store_true", help="expand pods in low-level")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    objs = load_objects(args)

    # index workloads by labels so we can match Services to backends
    workloads = []
    services  = []
    ingresses = []
    pods      = []
    endpoints = []

    for o in objs:
        k = kind(o)
        if workload_type(k):
            workloads.append(o)
        elif k == "Service":
            services.append(o)
        elif k == "Ingress":
            ingresses.append(o)
        elif k == "Pod":
            pods.append(o)
        elif k == "Endpoints" or k == "EndpointSlice":
            endpoints.append(o)

    # Build selectors → workload matches
    wl_by_ns = defaultdict(list)
    for w in workloads:
        wl_by_ns[ns(w)].append(w)

    svc_backends = defaultdict(list)  # svc_key -> [workload names]
    for s in services:
        sel = svc_selector(s)
        if not sel: 
            continue
        n = ns(s)
        candidates = wl_by_ns.get(n, [])
        for w in candidates:
            wl_labels = label_map(w)
            if all(wl_labels.get(k) == v for k, v in sel.items()):
                svc_backends[obj_key(s)].append(w)

    # ---------- High-level (C4 Context) template ----------
    c4_ctx = """@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml
title System Context - Your Platform

Person(user, "User", "Human using the platform")
System_Boundary(sys, "Your Platform") {
  System(system, "Kubernetes-based Data Platform", "Ingestion, Processing, Inference, Visualization")
}
Rel(user, system, "Uses", "HTTPS")
@enduml
"""
    open(os.path.join(args.outdir, "c4-context.puml"), "w").write(c4_ctx)

    # ---------- Mid-level (C4 Container) ----------
    # Namespaces as containers; Services and Workloads as components
    by_ns = defaultdict(lambda: {"services":[], "workloads":[]})
    for s in services:  by_ns[ns(s)]["services"].append(s)
    for w in workloads: by_ns[ns(w)]["workloads"].append(w)

    lines = []
    lines.append("@startuml")
    lines.append('!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml')
    lines.append('title Container View - Namespaces, Services, Workloads')
    lines.append('System_Boundary(k8s, "Kubernetes Cluster") {')
    for namespace, grp in sorted(by_ns.items()):
        lines.append(f'  Container_Boundary(ns_{namespace}, "Namespace: {namespace}") {{')
        for s in grp["services"]:
            lines.append(f'    Container(svc_{name(s)}_{namespace}, "Service: {name(s)}", "K8s Service")')
        for w in grp["workloads"]:
            lines.append(f'    Container(wl_{name(w)}_{namespace}, "{kind(w)}: {name(w)}", "K8s Workload")')
        lines.append('  }')
    # Edges: Service -> Workload (backends), Ingress -> Service
    for s in services:
        skey = obj_key(s)
        for w in svc_backends.get(skey, []):
            lines.append(f'Rel(svc_{name(s)}_{ns(s)}, wl_{name(w)}_{ns(w)}, "routes to")')
    for ing in ingresses:
        # ingress → the service(s) in rules
        ns_ing = ns(ing)
        rules = ing.get("spec", {}).get("rules", [])
        # best-effort parse of backend services (v1 Ingress)
        for r in rules:
            paths = r.get("http", {}).get("paths", [])
            for p in paths:
                b = p.get("backend", {})
                svc = b.get("service", {})
                svcname = svc.get("name")
                if svcname:
                    lines.append(f'Boundary(ing_{name(ing)}_{ns_ing}, "Ingress: {name(ing)}")')
                    lines.append(f'Rel(ing_{name(ing)}_{ns_ing}, svc_{svcname}_{ns_ing}, "forwards")')
    lines.append("}")
    lines.append("@enduml")
    open(os.path.join(args.outdir, "c4-container.puml"), "w").write("\n".join(lines))

    # ---------- Low-level (K8s topology) ----------
    # Use generic nodes/edges; optionally expand to pods
    low = []
    low.append("@startuml")
    low.append("title Kubernetes Topology - Services ↔ Workloads")
    low.append("skinparam linetype ortho")

    def n_id(prefix, o): return f'{prefix}_{name(o)}_{ns(o)}'
    for s in services:
        low.append(f'node "{ns(s)}/svc/{name(s)}" as {n_id("svc",s)}')
    for w in workloads:
        low.append(f'component "{ns(w)}/{kind(w)}/{name(w)}" as {n_id("wl",w)}')
    if args.include_pods:
        for p in pods:
            low.append(f'() "{ns(p)}/pod/{name(p)}" as {n_id("pod",p)}')

    for s in services:
        skey = obj_key(s)
        for w in svc_backends.get(skey, []):
            low.append(f'{n_id("svc",s)} --> {n_id("wl",w)} : routes')

    # naive pod link: pod ownerReference to workload (best-effort)
    if args.include_pods:
        for p in pods:
            owners = p.get("metadata", {}).get("ownerReferences", []) or []
            for oref in owners:
                oname = oref.get("name")
                okind = oref.get("kind")
                # link if we find matching workload
                for w in workloads:
                    if ns(w) == ns(p) and name(w) == oname and kind(w) == okind:
                        low.append(f'{n_id("wl",w)} --> {n_id("pod",p)} : controls')

    # ingress links already done in mid-level; repeat here as nodes
    for ing in ingresses:
        low.append(f'cloud "{ns(ing)}/ing/{name(ing)}" as {n_id("ing",ing)}')
        ns_ing = ns(ing)
        rules = ing.get("spec", {}).get("rules", [])
        for r in rules:
            paths = r.get("http", {}).get("paths", [])
            for p in paths:
                b = p.get("backend", {})
                svc = b.get("service", {})
                svcname = svc.get("name")
                if svcname:
                    low.append(f'{n_id("ing",ing)} --> svc_{svcname}_{ns_ing} : forwards')

    low.append("@enduml")
    open(os.path.join(args.outdir, "k8s-topology.puml"), "w").write("\n".join(low))

    print(f"Wrote {args.outdir}/c4-context.puml")
    print(f"Wrote {args.outdir}/c4-container.puml")
    print(f"Wrote {args.outdir}/k8s-topology.puml")

if __name__ == "__main__":
    main()
