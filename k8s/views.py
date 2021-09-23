from django.shortcuts import render, redirect
from django.http import JsonResponse, QueryDict
from kubernetes import client, config
from dashboard import node_data
import os, hashlib, random, re
from k8sapi import k8s


# 内存单位字符串转换
def memorystr(strs):
    n = str(
        round(int(re.findall("\d+", strs)[0]) / 1024 / 1024, 1))
    return n


# Node展示
def node(request):
    return render(request, 'k8s/node.html')


def node_api(request):
    # 命名空间选择和命名空间表格使用
    if request.method == "GET":
        code = 0
        msg = ""
        auth_type = request.session.get("auth_type")
        token = request.session.get("token")
        k8s.load_auth_config(auth_type, token)
        core_api = client.CoreV1Api()
        search_key = request.GET.get("search_key")
        data = []
        cmr = node_data.node_resouces(core_api)

        try:
            # print("test")
            # print(type(core_api.list_node_with_http_info())) #返回格式为字典
            # print(core_api.list_node_with_http_info()[0].api_version)  # 因为list_node_with_http_info返回是一个元组所以要加[0] 获取字典格式

            for node in core_api.list_node_with_http_info()[0].items:
                name = node.metadata.name

                labels = node.metadata.labels
                create_time = node.metadata.creation_timestamp
                status = node.status.conditions[-1].status
                scheduler = ("是" if node.spec.unschedulable is None else "否")

                # 获取所有pod cpu与内存的资源正在使用量总和
                memory_requests = str(cmr[name]["memory_requests"])
                cpu_requests = str(cmr[name]["cpu_requests"])

                memory = node.status.capacity['memory']
                memory = memory_requests + "/" + memorystr(memory) + "GiB"  # 同下行作用

                # memory = memory_requests + "/" + str(
                #     round(int(re.findall("\d+", node.status.capacity['memory'])[0]) / 1024 / 1024, 1)) + "GiB"

                cpu = cpu_requests + "/" + node.status.capacity['cpu'] + "Core"

                kebelet_version = node.status.node_info.kubelet_version
                cri_version = node.status.node_info.container_runtime_version

                node = {"name": name, "labels": labels, "status": status,
                        "scheduler": scheduler, "cpu": cpu, "memory": memory,
                        "kebelet_version": kebelet_version, "cri_version": cri_version,
                        "create_time": create_time}
                # 根据搜索值返回数据
                if search_key:
                    if search_key in name:
                        data.append(node)
                else:
                    data.append(node)
                code = 0
                msg = "获取数据成功"
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有访问权限"
            else:
                msg = "获取数据失败"
        count = len(data)

        # 分页
        if request.GET.get('page'):
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit'))
            start = (page - 1) * limit
            end = page * limit
            data = data[start:end]

        res = {'code': code, 'msg': msg, 'count': count, 'data': data}
        return JsonResponse(res)


def node_details(request):
    auth_type = request.session.get("auth_type")
    token = request.session.get("token")
    k8s.load_auth_config(auth_type, token)
    core_api = client.CoreV1Api()

    node_name = request.GET.get("node_name", None)
    n_r = node_data.node_resouces(core_api, node_name)
    n_i = node_data.node_info(core_api, node_name)
    return render(request, 'k8s/node_details.html', {"node_name": node_name, "node_resouces": n_r, "node_info": n_i})


def node_details_pod_list(request):
    auth_type = request.session.get("auth_type")
    token = request.session.get("token")
    k8s.load_auth_config(auth_type, token)
    core_api = client.CoreV1Api()

    node_name = request.GET.get("node_name", None)

    data = []
    try:
        for pod in core_api.list_pod_for_all_namespaces().items:
            name = pod.spec.node_name
            pod_name = pod.metadata.name
            namespace = pod.metadata.namespace
            status = ("运行中" if pod.status.conditions[-1].status else "异常")
            host_network = pod.spec.host_network
            pod_ip = ("主机网络" if host_network else pod.status.pod_ip)
            create_time = k8s.dt_format(pod.metadata.creation_timestamp)
            cpu_requests = "未配置CPU资源"
            cpu_limits = "CPU无限制"
            memory_requests = "未配置内存资源"
            memory_limits = "内存无限制"

            if name == node_name:
                # 循环字典查看pod里面有几个容器
                if len(pod.spec.containers) == 1:
                    for c in pod.spec.containers:
                        if c.resources.requests is not None:
                            if "cpu" in c.resources.requests:
                                cpu_requests = c.resources.requests["cpu"]
                            if "memory" in c.resources.requests:
                                memory_requests = c.resources.requests["memory"]
                        if c.resources.limits is not None:
                            if "cpu" in c.resources.limits:
                                cpu_limits = c.resources.limits["cpu"]
                            if "memory" in c.resources.limits:
                                memory_limits = c.resources.limits["memory"]

                else:
                    c_r = "未配置CPU资源"
                    c_l = "CPU无限制"
                    m_r = "未配置内存资源"
                    m_l = "内存无限制"
                    cpu_requests = ""
                    cpu_limits = ""
                    memory_requests = ""
                    memory_limits = ""
                    for c in pod.spec.containers:
                        c_name = c.name
                        # c_image= c.image
                        if c.resources.requests is not None:
                            if "cpu" in c.resources.requests:
                                c_r = c.resources.requests["cpu"]
                            if "memory" in c.resources.requests:
                                m_r = c.resources.requests["memory"]
                        if c.resources.limits is not None:
                            if "cpu" in c.resources.limits:
                                c_l = c.resources.limits["cpu"]
                            if "memory" in c.resources.limits:
                                m_l = c.resources.limits["memory"]

                        cpu_requests += "%s=%s<br>" % (c_name, c_r)
                        cpu_limits += "%s=%s<br>" % (c_name, c_l)
                        memory_requests += "%s=%s<br>" % (c_name, m_r)
                        memory_limits += "%s=%s<br>" % (c_name, m_l)

                pod = {"pod_name": pod_name, "namespace": namespace, "status": status, "pod_ip": pod_ip,
                       "cpu_requests": cpu_requests, "cpu_limits": cpu_limits, "memory_requests": memory_requests,
                       "memory_limits": memory_limits, "create_time": create_time}
                data.append(pod)

        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit'))
        start = (page - 1) * limit
        end = page * limit
        data = data[start:end]
        count = len(data)
        code = 0
        msg = "获取数据成功"
        res = {"code": code, "msg": msg, "count": count, "data": data}
        return JsonResponse(res)
    except Exception as e:
        print(e)
        status = getattr(e, "status")
        if status == 403:
            msg = "没有访问权限！"
        else:
            msg = "查询失败！"
        res = {"code": 1, "msg": msg}
        return JsonResponse(res)


# PV展示
def pv(request):
    return render(request, 'k8s/pv.html')


def pv_create(request):
    return render(request, 'k8s/pv_create.html')


def pv_api(request):
    code = 0
    msg = ""
    auth_type = request.session.get("auth_type")
    token = request.session.get("token")
    k8s.load_auth_config(auth_type, token)
    core_api = client.CoreV1Api()
    # 命名空间选择和命名空间表格使用
    if request.method == "GET":
        search_key = request.GET.get("search_key")
        data = []
        try:
            for pv in core_api.list_persistent_volume().items:
                name = pv.metadata.name
                capacity = pv.spec.capacity["storage"]
                access_modes = pv.spec.access_modes
                reclaim_policy = pv.spec.persistent_volume_reclaim_policy
                status = pv.status.phase
                if pv.spec.claim_ref is not None:
                    pvc_ns = pv.spec.claim_ref.namespace
                    pvc_name = pv.spec.claim_ref.name
                    pvc = "%s/%s" % (pvc_ns, pvc_name)
                else:
                    pvc = "未绑定"
                storage_class = pv.spec.storage_class_name
                create_time = pv.metadata.creation_timestamp
                pv = {"name": name, "capacity": capacity, "access_modes": access_modes,
                      "reclaim_policy": reclaim_policy, "status": status, "pvc": pvc,
                      "storage_class": storage_class, "create_time": create_time}
                # 根据搜索值返回数据
                if search_key:
                    if search_key in pvc_name:
                        data.append(pv)
                    if search_key in name:
                        data.append(pv)
                else:
                    data.append(pv)
                code = 0
                msg = "获取数据成功"
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有访问权限"
            else:
                msg = "获取数据失败"
        count = len(data)

        # 分页
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit'))
        start = (page - 1) * limit
        end = page * limit
        data = data[start:end]

        res = {'code': code, 'msg': msg, 'count': count, 'data': data}
        return JsonResponse(res)

    elif request.method == "POST":
        name = request.POST.get("name", None)
        capacity = request.POST.get("capacity", None)
        access_mode = request.POST.get("access_mode", None)
        storage_type = request.POST.get("storage_type", None)
        server_ip = request.POST.get("server_ip", None)
        mount_path = request.POST.get("mount_path", None)
        body = client.V1PersistentVolume(
            api_version="v1",
            kind="PersistentVolume",
            metadata=client.V1ObjectMeta(name=name),
            spec=client.V1PersistentVolumeSpec(
                capacity={'storage': capacity},
                access_modes=[access_mode],
                nfs=client.V1NFSVolumeSource(
                    server=server_ip,
                    path="/ifs/kubernetes/%s" % mount_path
                )
            )
        )
        try:
            core_api.create_persistent_volume(body=body)
            code = 0
            msg = "创建成功."
        except Exception as e:
            print(e)
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有访问权限！"
            else:
                msg = "创建失败！"
        res = {'code': code, 'msg': msg}
        return JsonResponse(res)

    elif request.method == "DELETE":
        request_data = QueryDict(request.body)
        name = request_data.get("name")
        auth_type = request.session.get("auth_type")
        token = request.session.get("token")
        k8s.load_auth_config(auth_type, token)
        core_api = client.CoreV1Api()
        try:
            core_api.delete_persistent_volume(name)
            code = 0
            msg = "删除成功."
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有删除权限"
            else:
                msg = "删除失败！"
        res = {'code': code, 'msg': msg}
        return JsonResponse(res)
