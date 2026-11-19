// Both point and non-point menus use the same route relationship, including
// external approach sections. A nearby flank point is not a train target.
export const matchingTrainRoutes = (routes, section) => routes.filter(route =>
  route.sections.includes(section) || route.approach_section === section)
