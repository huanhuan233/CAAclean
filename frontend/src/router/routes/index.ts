import type { CustomRoute, ElegantConstRoute, ElegantRoute } from '@elegant-router/types';
import { layouts, views } from '../elegant/imports';
import { transformElegantRoutesToVueRoutes } from '../elegant/transform';

const componentBuildRoute = {
  name: 'component-build',
  path: '/component-build',
  component: 'layout.base$view.component-build',
  meta: {
    title: '零件库',
    icon: 'carbon:tree-view-alt',
    order: 1
  }
} as unknown as CustomRoute;

const featureCenterRoute = {
  name: 'feature-center',
  path: '/feature-center',
  component: 'layout.base$view.feature-center',
  meta: {
    title: 'Feature Center',
    icon: 'carbon:3d-mpr-toggle',
    order: 3
  }
} as unknown as CustomRoute;

const customRoutes: CustomRoute[] = [componentBuildRoute, featureCenterRoute];

/** create routes when the auth route mode is static */
export function createStaticRoutes() {
  const constantRoutes: ElegantRoute[] = [];
  const authRoutes: ElegantRoute[] = [];

  customRoutes.forEach(item => {
    if (item.meta?.constant) {
      constantRoutes.push(item);
    } else {
      authRoutes.push(item);
    }
  });

  return {
    constantRoutes,
    authRoutes
  };
}

/**
 * Get auth vue routes
 *
 * @param routes Elegant routes
 */
export function getAuthVueRoutes(routes: ElegantConstRoute[]) {
  return transformElegantRoutesToVueRoutes(routes, layouts, views);
}
