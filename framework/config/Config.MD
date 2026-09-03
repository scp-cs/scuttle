# Framework configuration

The files inside this directory allow you to customize some parts of SCUTTLE, for example when adding modules or modifying your branch rules

## menu.yaml
This file lists the items shown in the sidebar menu, the entries are formatted as follows:
```yaml
menu:
    - entry1:
        text: "Menu Entry One"
        icon: "bi-whatsapp"
        auth: "unauthorized"
        handler: "AmogusController.detonate"
```

- Entry name - Does nothing, only needs to be unique
- `text` - The text shown in the navigation bar
- `icon` - A [Bootstrap Icons](https://icons.getbootstrap.com/) class assigned to the icon that will be shown
- `auth` - Specifies who the menu entry should be shown to
    - `"authorized"` - Only shown to users who are logged in (currently just administrators)
    - `"unauthorized_only"` - Only shown to users who are not logged in
    - `"unauthorized"` - Shown to everyone
- `handler` - A route name accepted by Flask's [url_for()](https://flask.palletsprojects.com/en/stable/api/#flask.Flask.url_for) function, the menu button will redirect to this route

## roles.yaml
Specifies the properties of user roles, currently used for translator roles only.
Format:
```yaml
translator:
  min_points: 10
  no_role: 
    name: "No role"
    point_limit: 0
    badge_css: ""
  roles:
    - translator1:
      name: "Translator I"
      point_limit: 10
      badge_css: "bg-green-100"
    - translator2:
      name: "Translator II"
      point_limit: 20
      badge_css: "bg-green-300"
```
The top level key must be `translator` for now.

The `no_role` entry is the default for a user with no roles.

As above, the role keys are unused and only need to be unique.

Properties:
- `name` - The name of the role...
- `point_limit` - The minimum amount of points required to achieve this role. Must be unique across all roles
- `badge_css` - The CSS classes that will be added to the role badge for this role, Tailwind is configured to search this file so you may use Tailwind classes, but you may have to run `tailwindcss` again if the class has not been included in the processed CSS files yet

# acl.yaml

The Access Control Lists. Here you can set which permissions are required to access which parts of SCUTTLE. It contains sensible defaults, and adding arbitrary roles is not supported yet, so you probably won't need to modify it unless you're modifying the access control module itself.

The top level key must always be `lists`, the rest of the file is formatted as follows:

```yaml
lists:
  ControllerName:
    route_function_name:
      - ROLE
    route_fn_2:
      - ROLE1
      - ROLE2
```

The following roles are available:
- ADMIN
  - General administrator tasks, expands into a couple of different roles
- MASTER_ADMIN
  - The system operator, bypasses all other permission checks and cannot be revoked once granted
- MANAGE_ARTICLE_SELF
  - Allows modifying metadata for the user's own articles
- MANAGE_ARTICLE_ALL
  - Allows modifying metadata for all articles
- MANAGE_USERS
  - Allows adding/editing/modifying users
- VIEW_BACKUPS
  - Allows viewing the backup archive and downloading files from it
- MANAGE_BACKUPS
  - Allows reconfiguring WikiComma, starting a backup and deleting old backup archives
- ACCESS_RSS
  - Allows viewing the "New pages" list and adding articles from it
- API
  - Allows creating/deleting API keys and using the API
- DEBUG_LOW
  - Allows safe debug operations
- DEBUG_HIGH
  - Allows potentially unsafe debug operations and granting some of the other roles to users