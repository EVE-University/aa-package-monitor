import json

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.html import format_html

from app_utils.views import link_html, no_wrap_html, yesno_str

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_INCLUDE_PACKAGES,
    PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
)
from .models import Distribution

PACKAGE_LIST_FILTER_PARAM = "filter"


@login_required
@permission_required("package_monitor.basic_access")
def index(request):
    obj = Distribution.objects.first()
    updated_at = obj.updated_at if obj else None
    distributions_qs = Distribution.objects.currently_selected()
    filter = request.GET.get(PACKAGE_LIST_FILTER_PARAM)
    if not filter:
        app_count = Distribution.objects.currently_selected().outdated_count()
        filter = "outdated" if app_count and app_count > 0 else "current"

    context = {
        "app_title": __title__,
        "page_title": "Distribution packages",
        "updated_at": updated_at,
        "filter": filter,
        "all_count": distributions_qs.count(),
        "current_count": distributions_qs.filter(is_outdated=False).count(),
        "outdated_count": distributions_qs.outdated_count(),
        "unknown_count": distributions_qs.filter(is_outdated__isnull=True).count(),
        "include_packages": PACKAGE_MONITOR_INCLUDE_PACKAGES,
        "show_all_packages": PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
    }
    return render(request, "package_monitor/index.html", context)


@login_required
@permission_required("package_monitor.basic_access")
def package_list_data(request) -> JsonResponse:
    """Returns the packages as list in JSON.
    Specify different subsets with the "filter" GET parameter
    """
    my_filter = request.GET.get(PACKAGE_LIST_FILTER_PARAM, "")
    distributions_qs = Distribution.objects.currently_selected()

    if my_filter == "outdated":
        distributions_qs = distributions_qs.filter(is_outdated=True)
    elif my_filter == "current":
        distributions_qs = distributions_qs.filter(is_outdated=False)
    elif my_filter == "unknown":
        distributions_qs = distributions_qs.filter(is_outdated__isnull=True)

    data = list()
    for dist in distributions_qs.order_by("name"):
        name_link_html = (
            link_html(dist.website_url, dist.name) if dist.website_url else dist.name
        )
        if dist.is_outdated:
            name_link_html += '&nbsp;<i class="fas fa-exclamation-circle" title="Update available"></i>'

        if dist.apps:
            _lst = [no_wrap_html(row) for row in json.loads(dist.apps)]
            apps_html = "<br>".join(_lst) if _lst else "-"
        else:
            apps_html = ""

        if dist.used_by:
            used_by_sorted = sorted(json.loads(dist.used_by), key=lambda k: k["name"])
            used_by_html = "<br>".join(
                [
                    format_html(
                        '<span title="{}" style="white-space: nowrap;">{}</span>',
                        ", ".join(row["requirements"])
                        if row["requirements"]
                        else "ANY",
                        link_html(row["homepage_url"], row["name"])
                        if row["homepage_url"]
                        else row["name"],
                    )
                    for row in used_by_sorted
                ]
            )
        else:
            used_by_html = ""

        if not dist.latest_version:
            latest_html = "?"
        else:
            command = f"pip install {dist.pip_install_version}"
            latest_html = no_wrap_html(
                f'<span class="copy_to_clipboard" '
                f'title="Click to copy install command to clipboard"'
                f' data-text="{command}">'
                f"{dist.latest_version}"
                '&nbsp;&nbsp;<i class="far fa-copy"></i></span>'
            )

        data.append(
            {
                "name": dist.name,
                "name_link": no_wrap_html(name_link_html),
                "apps": apps_html,
                "used_by": used_by_html,
                "current": dist.installed_version,
                "latest": latest_html,
                "is_outdated": dist.is_outdated,
                "is_outdated_str": yesno_str(dist.is_outdated),
                "description": dist.description,
            }
        )

    return JsonResponse(data, safe=False)


@login_required
@permission_required("package_monitor.basic_access")
def refresh_distributions(request):
    Distribution.objects.update_all(use_threads=True)
    return HttpResponse("ok")
